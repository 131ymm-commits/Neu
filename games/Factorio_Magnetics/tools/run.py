"""Прогон мода на headless-сервере Factorio: создать карту с модом, прокрутить N тиков (--benchmark),
собрать script-output тестового мода и лог. Конфигурации: base (только базовая игра) и sa (Space Age + quality + elevated-rails).
Сервер: /opt/factorio (2.0.77, скачивается с factorio.com/get-download/stable/headless/linux64)."""
import json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FACTORIO = os.environ.get('FACTORIO', '/opt/factorio')
BIN = os.path.join(FACTORIO, 'bin/x64/factorio')
MOD_SRC = os.path.join(ROOT, 'magnetics')
TESTS_SRC = os.path.join(HERE, 'magnetics-tests')

def mod_version(path):
    return json.load(open(os.path.join(path, 'info.json')))['version']

def prepare(cfg, work, with_tests=True, extra_mods=(), select=None):
    os.makedirs(work, exist_ok=True)
    mods = os.path.join(work, 'mods'); shutil.rmtree(mods, ignore_errors=True); os.makedirs(mods)
    shutil.copytree(MOD_SRC, os.path.join(mods, f'magnetics_{mod_version(MOD_SRC)}'))
    if with_tests:
        td = os.path.join(mods, f'magnetics-tests_{mod_version(TESTS_SRC)}')
        shutil.copytree(TESTS_SRC, td)
        if select is not None:
            open(os.path.join(td, 'cells', '_select.lua'), 'w').write('return {' + ', '.join('"%s"' % s for s in select) + '}\n')
    for m in extra_mods: shutil.copytree(m, os.path.join(mods, os.path.basename(m)))
    on = {'base': (), 'bq': ('quality',), 'be': ('elevated-rails',), 'sa': ('elevated-rails', 'quality', 'space-age')}[cfg]
    lst = [{'name': 'base', 'enabled': True}] + [{'name': n, 'enabled': n in on} for n in ('elevated-rails', 'quality', 'space-age')]
    lst += [{'name': 'magnetics', 'enabled': True}, {'name': 'magnetics-tests', 'enabled': with_tests}]
    json.dump({'mods': lst}, open(os.path.join(mods, 'mod-list.json'), 'w'))
    wd = os.path.join(work, 'wd'); shutil.rmtree(wd, ignore_errors=True)
    open(os.path.join(work, 'config.ini'), 'w').write(f'[path]\nread-data={FACTORIO}/data\nwrite-data={wd}\n')
    return mods, wd

def run(cfg='base', ticks=600, work=None, with_tests=True, keep=False, extra_mods=(), select=None):
    work = work or tempfile.mkdtemp(prefix=f'mgn_{cfg}_')
    mods, wd = prepare(cfg, work, with_tests, extra_mods, select)
    base = [BIN, '-c', os.path.join(work, 'config.ini'), '--mod-directory', mods]
    save = os.path.join(work, 'test.zip')
    r1 = subprocess.run(base + ['--create', save, '--map-gen-seed', '20260930'], capture_output=True, text=True, timeout=600)
    log1 = open(os.path.join(wd, 'factorio-current.log'), encoding='utf-8', errors='replace').read()
    res = dict(cfg=cfg, work=work, create_ok=r1.returncode == 0 and os.path.exists(save), create_log=log1)
    if res['create_ok'] and ticks:
        r2 = subprocess.run(base + ['--benchmark', save, '--benchmark-ticks', str(ticks)], capture_output=True, text=True, timeout=3600)
        res['bench_out'] = r2.stdout + r2.stderr
        res['bench_ok'] = r2.returncode == 0 and 'Performed' in r2.stdout
        res['bench_log'] = open(os.path.join(wd, 'factorio-current.log'), encoding='utf-8', errors='replace').read()
    out = {}
    so = os.path.join(wd, 'script-output')
    if os.path.isdir(so):
        for f in os.listdir(so):
            txt = open(os.path.join(so, f), encoding='utf-8').read()
            try: out[f] = json.loads(txt)
            except Exception: out[f] = txt
    res['output'] = out
    res['errors'] = [l for l in (log1 + res.get('bench_log', '')).splitlines() if re.search(r'\bError\b|non-recoverable|Failed to load|stack traceback', l)]
    res['warnings'] = [l for l in (log1 + res.get('bench_log', '')).splitlines() if re.search(r'\bWarning\b', l)]
    m = re.search(r'MAGNETICS_RAW_BEGIN(.*?)MAGNETICS_RAW_END', log1, re.S)
    if m:
        open(os.path.join(work, 'raw.json'), 'w').write(m.group(1)); res['raw'] = os.path.join(work, 'raw.json')
    return res

if __name__ == '__main__':
    cfg = sys.argv[1] if len(sys.argv) > 1 else 'base'
    ticks = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    select = sys.argv[3].split(',') if len(sys.argv) > 3 else None
    r = run(cfg, ticks, select=select)
    res = r['output'].get('magnetics-results.json')
    if isinstance(res, dict):
        print('pass', res['pass'], 'fail', res['fail'])
        for x in res['results']:
            if not x['pass']: print('  FAIL', x['group'], x['name'], 'got', x.get('got'), 'exp', x.get('expected'), x.get('note') or '')
    print('create_ok', r['create_ok'], 'bench_ok', r.get('bench_ok'))
    for e in r['errors'][:30]: print('ERR', e)
    for w in r['warnings'][:10]: print('WARN', w)
    print('outputs:', list(r['output']))
    print('work:', r['work'])
