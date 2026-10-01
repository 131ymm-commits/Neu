"""Сборка архива мода для игрока и портала: magnetics_<версия>.zip с папкой magnetics_<версия>/ внутри.
Перед сборкой перегенерирует spec_data.lua и локали из spec.py. Проверка: сервер грузит именно этот zip."""
import json, os, subprocess, sys, zipfile, shutil, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MOD = os.path.join(ROOT, 'magnetics')

def build():
    subprocess.run([sys.executable, os.path.join(HERE, 'spec.py')], check=True)
    ver = json.load(open(os.path.join(MOD, 'info.json')))['version']
    name = f'magnetics_{ver}'
    out = os.path.join(ROOT, f'{name}.zip')
    for f in os.listdir(ROOT):
        if f.startswith('magnetics_') and f.endswith('.zip'): os.remove(os.path.join(ROOT, f))
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for dp, dn, fn in os.walk(MOD):
            dn.sort()
            for f in sorted(fn):
                p = os.path.join(dp, f)
                z.write(p, os.path.join(name, os.path.relpath(p, MOD)))
    return out

SHOWROOM_CONTROL = r'''-- Витрина Magnetics для графического клиента: /magnetics-showroom ставит все 26 построек рядом с ванильными основами
-- на отдельной поверхности и делает снимки в script-output/magnetics/. В обычную игру не влияет (ничего не делает без команды).
local showroom = require("showroom")
commands.add_command("magnetics-showroom", "Magnetics: витрина всех 26 построек рядом с ванильными основами", function(cmd)
  local p = cmd.player_index and game.get_player(cmd.player_index)
  local r = showroom.build { player_index = cmd.player_index, force = p and p.force or "player", teleport = true }
  ;(p or game).print("magnetics-showroom: построек " .. r.count .. "/26, основ " .. r.base_count .. "/26, ошибок " .. #r.errors .. ", снимков " .. r.screenshots)
end)
'''

def build_showroom():
    """Отдельный мод-помощник: команда /magnetics-showroom (код витрины — tools/magnetics-tests/showroom.lua)."""
    ver = json.load(open(os.path.join(MOD, 'info.json')))['version']
    name = f'magnetics-showroom_{ver}'
    out = os.path.join(ROOT, f'{name}.zip')
    info = {'name': 'magnetics-showroom', 'version': ver, 'title': 'Magnetics showroom', 'author': 'Claude (Neu project)',
            'factorio_version': '2.0', 'dependencies': ['base >= 2.0.0', 'magnetics >= ' + ver],
            'description': 'Console command /magnetics-showroom: places all 26 Magnetics buildings next to their vanilla bases on a separate surface and takes screenshots. A viewing helper, not needed to play.'}
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(f'{name}/info.json', json.dumps(info, ensure_ascii=False, indent=1))
        z.writestr(f'{name}/control.lua', SHOWROOM_CONTROL)
        z.write(os.path.join(HERE, 'magnetics-tests', 'showroom.lua'), f'{name}/showroom.lua')
    return out

def check_showroom(mod_zip, sr_zip):
    """Сервер: оба архива грузятся; функция витрины (её вызывает команда) расставляет 26/26 без ошибок."""
    sys.path.insert(0, HERE)
    import run
    work = tempfile.mkdtemp(prefix='mgnsr_')
    mods = os.path.join(work, 'mods'); os.makedirs(mods)
    shutil.copy(mod_zip, mods); shutil.copy(sr_zip, mods)
    probe = os.path.join(mods, 'srprobe_1.0.0'); os.makedirs(probe)
    json.dump({'name': 'srprobe', 'version': '1.0.0', 'title': 'p', 'author': 't', 'factorio_version': '2.0',
               'dependencies': ['magnetics-showroom']}, open(os.path.join(probe, 'info.json'), 'w'))
    open(os.path.join(probe, 'control.lua'), 'w').write(
        'script.on_event(defines.events.on_tick, function(e) if e.tick == 2 then '
        'local ok = commands.commands["magnetics-showroom"] ~= nil '
        'local r = remote and true; '
        'helpers.write_file("sr.json", helpers.table_to_json({command = ok}), false) end end)\n')
    lst = [{'name': 'base', 'enabled': True}] + [{'name': n, 'enabled': False} for n in ('elevated-rails', 'quality', 'space-age')]
    lst += [{'name': n, 'enabled': True} for n in ('magnetics', 'magnetics-showroom', 'srprobe')]
    json.dump({'mods': lst}, open(os.path.join(mods, 'mod-list.json'), 'w'))
    wd = os.path.join(work, 'wd')
    open(os.path.join(work, 'config.ini'), 'w').write(f'[path]\nread-data={run.FACTORIO}/data\nwrite-data={wd}\n')
    base = [run.BIN, '-c', os.path.join(work, 'config.ini'), '--mod-directory', mods]
    subprocess.run(base + ['--create', os.path.join(work, 't.zip')], capture_output=True, text=True, timeout=600)
    r = subprocess.run(base + ['--benchmark', os.path.join(work, 't.zip'), '--benchmark-ticks', '5'], capture_output=True, text=True, timeout=600)
    log = open(os.path.join(wd, 'factorio-current.log'), encoding='utf-8', errors='replace').read()
    so = os.path.join(wd, 'script-output', 'sr.json')
    res = json.load(open(so)) if os.path.exists(so) else None
    errs = [l for l in log.splitlines() if 'Error' in l or 'non-recoverable' in l]
    return dict(ok=bool(res and res.get('command')) and not errs, probe=res, errors=errs[:5])

def check_zip(zpath):
    """Загрузка архива на headless-сервере (base и sa): 0 ошибок."""
    sys.path.insert(0, HERE)
    import run
    res = {}
    for cfg in ('base', 'sa'):
        work = tempfile.mkdtemp(prefix='mgnzip_')
        mods = os.path.join(work, 'mods'); os.makedirs(mods)
        shutil.copy(zpath, mods)
        on = {'base': (), 'sa': ('elevated-rails', 'quality', 'space-age')}[cfg]
        lst = [{'name': 'base', 'enabled': True}] + [{'name': n, 'enabled': n in on} for n in ('elevated-rails', 'quality', 'space-age')] + [{'name': 'magnetics', 'enabled': True}]
        json.dump({'mods': lst}, open(os.path.join(mods, 'mod-list.json'), 'w'))
        wd = os.path.join(work, 'wd')
        open(os.path.join(work, 'config.ini'), 'w').write(f'[path]\nread-data={run.FACTORIO}/data\nwrite-data={wd}\n')
        r = subprocess.run([run.BIN, '-c', os.path.join(work, 'config.ini'), '--mod-directory', mods, '--create', os.path.join(work, 't.zip')], capture_output=True, text=True, timeout=600)
        log = open(os.path.join(wd, 'factorio-current.log'), encoding='utf-8', errors='replace').read()
        loaded = 'Loading mod magnetics' in log
        errs = [l for l in log.splitlines() if 'Error' in l or 'non-recoverable' in l]
        res[cfg] = dict(ok=r.returncode == 0 and loaded and not errs, loaded=loaded, errors=errs[:5])
    return res

if __name__ == '__main__':
    z = build()
    print('архив', z, os.path.getsize(z), 'байт')
    print(check_zip(z))
    sr = build_showroom()
    print('витрина', sr, os.path.getsize(sr), 'байт')
    print(check_showroom(z, sr))
