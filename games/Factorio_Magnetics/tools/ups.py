"""Цена ремонтной катушки по скорости игры (FINAL_SPEC §11.9, U1/U2; шум — PILOT-20, §14 и §15.2).
Отдельный мод-сценарий строит карту в on_init, затем --benchmark N тиков; берётся «avg: X ms» (среднее мс на тик).
Каждый вариант — RUNS прогонов (варианты чередуются), сравниваются медианы.
U1: 10 000 стен + 200 простаивающих запитанных катушек минус та же карта с 200 незапитанными аккумуляторами: Δ ≤ 0,02 мс/тик.
    В обоих вариантах одна и та же электросеть (источник + подстанции, ревью c23); в контроле она стоит в стороне
    и аккумуляторы не питает (§11.9: «unpowered accumulators»).
U2: 100 катушек вокруг 1000 стен, каждые 60 тиков урон 50 стенам (фиксированный порядок), минус та же карта без катушек
    (та же электросеть в обоих вариантах): Δ ≤ 0,10 мс/тик.
Шум (PILOT-20) — только по контрольным вариантам (A/A: U1acc и U2none): наибольший разброс max − min отдельных
прогонов одного варианта. Опытные варианты (U1coil, U2coil) в шум не входят: выброс в них не ослабляет свой порог.
Запуск: python3 tools/ups.py [runs] [ticks]  →  tools/ups_results.json (его читает tools/tests.py: U1, U2)"""
import datetime, hashlib, json, os, re, shutil, statistics, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run  # noqa: E402

CONTROL = r'''
local V = "%s"
local function lab()
  local S = game.create_surface("ups", {width = 512, height = 512})
  S.generate_with_lab_tiles = true
  S.request_to_generate_chunks({0, 0}, 8); S.force_generate_chunk_requests()
  return S
end
local function power(S, x0, y0, w, h)
  local src = S.create_entity{name = "electric-energy-interface", position = {x0 - 4, y0 - 4}, force = "player"}
  src.power_production = 1e9 / 60; src.electric_buffer_size = 1e9
  for x = x0 - 2, x0 + w + 2, 16 do for y = y0 - 2, y0 + h + 2, 16 do
    S.create_entity{name = "substation", position = {x, y}, force = "player"} end end
end
script.on_init(function()
  local S = lab()
  storage.walls = {}
  if V == "U1coil" or V == "U1acc" then
    -- 10 000 стен в квадрате 100×100 (простой фон), 200 катушек или аккумуляторов отдельным блоком
    for i = 0, 9999 do S.create_entity{name = "stone-wall", position = {-150 + i %% 100, -150 + math.floor(i / 100)}, force = "player"} end
    -- одна и та же сеть (источник + 15 подстанций) в обоих вариантах: меряется цена катушек, а не подстанций (ревью c23).
    -- В контроле сеть сдвинута на 100 клеток (подстанции на y 98..130, зона ±9) и аккумуляторы (y 1..29) не питает.
    if V == "U1coil" then power(S, 0, 0, 60, 30) else power(S, 0, 100, 60, 30) end
    for i = 0, 199 do
      S.create_entity{name = V == "U1coil" and "magnetics-mend-coil" or "accumulator", position = {1 + (i %% 20) * 3, 1 + math.floor(i / 20) * 3}, force = "player",
                      raise_built = true}
    end
  else
    -- 1000 стен сеткой 50×20 через клетку; 100 катушек между ними (U2coil) или без них (U2none)
    for i = 0, 999 do
      local w = S.create_entity{name = "stone-wall", position = {(i %% 50) * 2, math.floor(i / 50) * 4}, force = "player"}
      storage.walls[#storage.walls + 1] = w
    end
    power(S, 0, 0, 100, 80)   -- одна и та же сеть в обоих вариантах: меряется цена катушек, а не подстанций
    if V == "U2coil" then
      for i = 0, 99 do
        S.create_entity{name = "magnetics-mend-coil", position = {(i %% 10) * 10 + 1, math.floor(i / 10) * 8 + 2}, force = "player", raise_built = true}
      end
    end
  end
  storage.k = 0
end)
script.on_nth_tick(60, function()
  if V == "U2coil" or V == "U2none" then
    local ws = storage.walls
    for j = 1, 50 do
      storage.k = (storage.k * 37 + 11) %% #ws          -- фиксированная псевдослучайная последовательность
      local w = ws[storage.k + 1]
      -- одинаковая нагрузка в обоих вариантах: стена, просевшая ниже 100, восстанавливается сценарием,
      -- чтобы урон (и события урона) шли с той же частотой и без катушек
      if w.valid then
        if w.health < 100 then w.health = w.max_health end
        w.damage(40, "enemy", "physical")
      end
    end
  end
end)
'''

def bench(variant, ticks, work):
    w = os.path.join(work, variant + '_' + str(len(os.listdir(work))))
    mods = os.path.join(w, 'mods'); os.makedirs(mods)
    ver = run.mod_version(run.MOD_SRC)
    shutil.copytree(run.MOD_SRC, os.path.join(mods, f'magnetics_{ver}'))
    md = os.path.join(mods, 'magnetics-ups_1.0.0'); os.makedirs(md)
    json.dump({'name': 'magnetics-ups', 'version': '1.0.0', 'title': 'ups', 'author': 't', 'factorio_version': '2.0',
               'dependencies': ['base >= 2.0', 'magnetics']}, open(os.path.join(md, 'info.json'), 'w'))
    open(os.path.join(md, 'control.lua'), 'w').write(CONTROL % variant)
    lst = [{'name': 'base', 'enabled': True}] + [{'name': n, 'enabled': False} for n in ('elevated-rails', 'quality', 'space-age')]
    lst += [{'name': 'magnetics', 'enabled': True}, {'name': 'magnetics-ups', 'enabled': True}]
    json.dump({'mods': lst}, open(os.path.join(mods, 'mod-list.json'), 'w'))
    wd = os.path.join(w, 'wd')
    open(os.path.join(w, 'config.ini'), 'w').write(f'[path]\nread-data={run.FACTORIO}/data\nwrite-data={wd}\n')
    base = [run.BIN, '-c', os.path.join(w, 'config.ini'), '--mod-directory', mods]
    save = os.path.join(w, 's.zip')
    subprocess.run(base + ['--create', save, '--map-gen-seed', '20260930'], capture_output=True, text=True, timeout=600, check=True)
    r = subprocess.run(base + ['--benchmark', save, '--benchmark-ticks', str(ticks)], capture_output=True, text=True, timeout=1800)
    m = re.search(r'avg: ([0-9.]+) ms', r.stdout)
    if not m: raise RuntimeError(r.stdout[-2000:])
    shutil.rmtree(w, ignore_errors=True)
    return float(m.group(1))

CONTROLS = ('U1acc', 'U2none')      # контрольные варианты: только по ним считается шум (A/A)
PILOT20_RULE = ('PILOT-20 (FINAL_SPEC §14, §15.2): шум = наибольший разброс (max − min) отдельных прогонов одного контрольного '
                'варианта (U1acc, U2none; опытные U1coil и U2coil не входят). Порог спецификации годен, если он ≥ 3 × шум; иначе '
                'медианная разность сравнивается с 3 × шум и вердикт помечается resolvable = false (порог на этой машине неразличим).')
LIMITATION = ('шум берётся из тех же прогонов, а не из отдельного пилота до регистрации (§14); max − min по 5 прогонам '
              'определяется одним выбросом')



# ---------------------------------------------------------------------------------------------------------------
# Цена самого скрипта катушки профайлером Factorio (helpers.create_profiler): копия мода, в которой цикл лечения и
# обработчик урона обёрнуты накопительным профайлером; карта U2coil, 3000 тиков. Не зависит от шума остальной
# симуляции (разность «с катушками и без» на шумной машине неразличима, см. PILOT-20).
def inject_profiler(control_path):
    s = open(control_path, encoding='utf-8').read()
    s = s.replace('local floor = math.floor', 'local floor = math.floor\nlocal PROF\n'
                  'local function prof_get() if not PROF then PROF = helpers.create_profiler(true) end return PROF end', 1)
    s = s.replace('script.on_nth_tick(PERIOD, on_cycle)',
                  'script.on_nth_tick(PERIOD, function(ev) local P = prof_get(); P.restart(); on_cycle(ev); P.stop()\n'
                  '  if ev.tick == TICKS_END then log({"", "PROFTOTAL ", P}) end end)')
    s = s.replace('script.on_event(defines.events.on_entity_damaged, on_damaged, DAMAGE_FILTER)',
                  'script.on_event(defines.events.on_entity_damaged, function(e) local P = prof_get(); P.restart(); on_damaged(e); P.stop() end, DAMAGE_FILTER)')
    assert s.count('prof_get()') == 2 + 1, 'не удалось встроить профайлер: изменилась структура control.lua'
    open(control_path, 'w', encoding='utf-8').write(s)

def script_profile(runs=3, ticks=3000):
    vals = []
    for i in range(runs):
        work = tempfile.mkdtemp(prefix='mgn_prof_')
        src = os.path.join(work, 'magnetics_src'); shutil.copytree(run.MOD_SRC, src)
        inject_profiler(os.path.join(src, 'control.lua'))
        cp = os.path.join(src, 'control.lua'); t = open(cp).read().replace('TICKS_END', str(ticks - ticks % 30 - 30)); open(cp, 'w').write(t)
        saved = run.MOD_SRC; run.MOD_SRC = src
        keep = shutil.rmtree; shutil.rmtree = lambda *a, **k: None
        try:
            bench('U2coil', ticks, work)
        finally:
            shutil.rmtree = keep; run.MOD_SRC = saved
        for dp, dn, fn in os.walk(work):
            for f in fn:
                if f == 'factorio-current.log':
                    m = re.search(r'PROFTOTAL Duration: ([0-9.]+)ms', open(os.path.join(dp, f), encoding='utf-8', errors='replace').read())
                    if m: vals.append(float(m.group(1)) / ticks)
        shutil.rmtree(work, ignore_errors=True)
    return vals

def main(runs=5, ticks=3000):
    work = tempfile.mkdtemp(prefix='mgn_ups_')
    started = datetime.datetime.now().isoformat(timespec='seconds')
    res = {}
    # чередуем варианты, чтобы медленный дрейф машины не ложился на один вариант
    order = ['U1acc', 'U1coil', 'U2none', 'U2coil']
    for i in range(runs):
        for v in order:
            res.setdefault(v, []).append(bench(v, ticks, work))
            print(v, i, res[v][-1], flush=True)
    med = {v: statistics.median(x) for v, x in res.items()}
    spread = {v: round(max(x) - min(x), 6) for v, x in res.items()}
    noise = max(spread[v] for v in CONTROLS)

    def verdict(delta, limit):
        # правило PILOT-20 записано до замера (§14): порог годен, только если он не меньше 3× шума
        resolvable = limit >= 3 * noise
        eff = limit if resolvable else 3 * noise
        return dict(delta=round(delta, 4), limit=limit, noise=round(noise, 4), resolvable=resolvable, effective_limit=round(eff, 4),
                    ok=delta <= eff)
    out = dict(started=started, runs=runs, ticks=ticks, ms=res, median=med, spread=spread,
               noise_from=list(CONTROLS), noise=round(noise, 4), pilot20_rule=PILOT20_RULE, limitation=LIMITATION,
               U1=verdict(med['U1coil'] - med['U1acc'], 0.02),
               U2=verdict(med['U2coil'] - med['U2none'], 0.10),
               mod_control_sha256=hashlib.sha256(open(os.path.join(run.MOD_SRC, 'control.lua'), 'rb').read()).hexdigest(),
               configuration='base (quality, elevated-rails, space-age выключены; §11.1 называет B и SA — сужение)',
               networks='U1: источник + 15 подстанций в обоих вариантах (в U1acc сдвинуты, аккумуляторы без питания); '
                        'U2: одна сеть в обоих вариантах',
               noise_note='шум = наибольший разброс (max − min) прогонов одного контрольного варианта (U1acc, U2none)')
    prof = script_profile(3, ticks)
    out['U2_script_ms_per_tick'] = dict(runs=[round(v, 4) for v in prof], median=round(statistics.median(prof), 4) if prof else None,
        limit=0.10, ok=bool(prof) and statistics.median(prof) <= 0.10,
        note='время самого скрипта катушки (цикл лечения + обработчик урона) на карте U2coil, профайлер Factorio; '
             'сущности катушек сверх этого стоят около 0,02 мс/тик (разложение 01.10.2026)')
    json.dump(out, open(os.path.join(HERE, 'ups_results.json'), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps({k: out[k] for k in ('median', 'spread', 'noise_from', 'noise', 'U1', 'U2')}, indent=1, ensure_ascii=False))
    shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 5, int(sys.argv[2]) if len(sys.argv) > 2 else 3000)
