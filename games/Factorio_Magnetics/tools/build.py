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
