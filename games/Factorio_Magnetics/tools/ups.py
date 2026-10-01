"""Цена ремонтной катушки по скорости игры (FINAL_SPEC §11.9, U1/U2; шум — PILOT-20).
Отдельный мод-сценарий строит карту в on_init, затем --benchmark N тиков; берётся «avg: X ms» (среднее мс на тик).
Каждый вариант — RUNS прогонов, сравниваются медианы. Шум: разброс медиан одного и того же варианта (A/A).
U1: 10 000 стен + 200 простаивающих запитанных катушек минус та же карта с 200 незапитанными аккумуляторами: Δ ≤ 0,02 мс/тик.
U2: 100 катушек вокруг 1000 стен, каждые 60 тиков урон 50 стенам (фиксированный порядок), минус та же карта без катушек
(та же электросеть в обоих вариантах): Δ ≤ 0,10 мс/тик.
Запуск: python3 tools/ups.py [runs] [ticks]"""
import json, os, re, shutil, statistics, subprocess, sys, tempfile

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
    if V == "U1coil" then power(S, 0, 0, 60, 30) end
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

def main(runs=5, ticks=3000):
    work = tempfile.mkdtemp(prefix='mgn_ups_')
    res = {}
    # чередуем варианты, чтобы медленный дрейф машины не ложился на один вариант
    order = ['U1acc', 'U1coil', 'U2none', 'U2coil']
    for i in range(runs):
        for v in order:
            res.setdefault(v, []).append(bench(v, ticks, work))
            print(v, i, res[v][-1], flush=True)
    med = {v: statistics.median(x) for v, x in res.items()}
    spread = {v: max(x) - min(x) for v, x in res.items()}
    noise = max(spread.values())
    def verdict(delta, limit):
        # PILOT-20 (FINAL_SPEC §14, правило записано до замера): порог годен, только если он не меньше 3× шума;
        # иначе разность сравнивается с 3× шума и это помечается как «порог на этой машине неразличим»
        resolvable = limit >= 3 * noise
        eff = limit if resolvable else 3 * noise
        return dict(delta=round(delta, 4), limit=limit, noise=round(noise, 4), resolvable=resolvable, effective_limit=round(eff, 4),
                    ok=delta <= eff)
    out = dict(runs=runs, ticks=ticks, ms=res, median=med, spread=spread,
               U1=verdict(med['U1coil'] - med['U1acc'], 0.02),
               U2=verdict(med['U2coil'] - med['U2none'], 0.10),
               noise_note='шум = наибольший разброс (max-min) прогонов одного варианта')
    json.dump(out, open(os.path.join(HERE, 'ups_results.json'), 'w'), indent=1)
    print(json.dumps({k: out[k] for k in ('median', 'spread', 'U1', 'U2')}, indent=1))
    shutil.rmtree(work, ignore_errors=True)

if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 5, int(sys.argv[2]) if len(sys.argv) > 2 else 3000)
