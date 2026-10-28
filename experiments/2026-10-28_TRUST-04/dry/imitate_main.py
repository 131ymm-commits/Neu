#!/usr/bin/env python3
"""TRUST-04: имитация ветки MAIN анализа (третья проверка по трём линзам, находка 2). Сухой прогон ветку MAIN не достаёт:
она требует тестовых зёрен 600–619 в папке опыта. Здесь — копия кода в рабочей папке (вне репозитория), куда кладутся
ячейки пилота v2, переразмеченные в 600–619 (каждое пилотное зерно дважды), и пилоты независимой реализации,
переразмеченные в 700–719; в json дописываются хеши кода и зависимостей и версии, как их пишет нынешний run(); затем
prereg_hashes.py и analyze_trust_04.py в копии. Модель на тестовых зёрнах не запускается.
Запуск из папки опыта: python3 dry/imitate_main.py РАБОЧАЯ_ПАПКА > dry/imitate_main.log"""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys

EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = sys.argv[1]
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
if os.path.exists(ROOT):
    shutil.rmtree(ROOT)
CE = os.path.join(ROOT, 'experiments', '2026-10-28_TRUST-04')
os.makedirs(os.path.join(CE, 'indep', 'test700'))
for name in ('2026-10-28_TRUST-01', '2026-10-28_TRUST-02', '2026-10-28_TRUST-03'):
    d = os.path.join(ROOT, 'experiments', name); os.makedirs(d)
    for f in os.listdir(os.path.join(EXP, '..', name)):
        if f.endswith('.py'):
            shutil.copy(os.path.join(EXP, '..', name, f), d)
for f in ('exp_trust_04.py', 'analyze_trust_04.py', 'indep_runner.py', 'prereg_hashes.py', 'requirements.txt',
          'indep/indep_trust_04.py', 'indep/SPEC.md', 'pilot/v2/pilot_calib2.py', 'pilot/v2/compare_v1.py',
          'pilot/v2/prereg_tables.py', 'pilot/v2/assemble_prereg.py'):
    os.makedirs(os.path.dirname(os.path.join(CE, f)), exist_ok=True); shutil.copy(os.path.join(EXP, f), os.path.join(CE, f))
deps = {f'../{n}/{m}': sha(os.path.join(CE, '..', n, m)) for n, m in (('2026-10-28_TRUST-01', 'exp_trust_01.py'), ('2026-10-28_TRUST-02', 'exp_trust_02.py'))}
import numpy, scipy  # noqa: E402,E401
vers = dict(numpy=numpy.__version__, scipy=scipy.__version__, python=sys.version.split()[0])
seeds = list(range(600, 620)); pil = list(range(1100, 1110))
for part in ('A', 'B'):
    d = json.load(open(os.path.join(EXP, 'pilot', 'v2', f'results_trust_04_{part}.json')))
    runs = []
    for i, s in enumerate(seeds):
        for r in d['runs']:
            if r['seed'] == pil[i % 10]:
                rr = copy.deepcopy(r); rr['seed'] = s; runs.append(rr)
    d['runs'] = runs
    d['params'].update(SEEDS=seeds, code_sha256=sha(os.path.join(CE, 'exp_trust_04.py')), deps_sha256=deps, versions=vers)
    json.dump(d, open(os.path.join(CE, f'results_trust_04_{part}.json'), 'w'))
ir = []
for sub in ('pilot', 'pilot1205'):
    ir += json.load(open(os.path.join(EXP, 'indep', sub, 'results_indep_04.json')))['runs']
base = json.load(open(os.path.join(EXP, 'indep', 'pilot1205', 'results_indep_04.json')))
ipil = list(range(1200, 1210)); iseeds = list(range(700, 720)); runs = []
for i, s in enumerate(iseeds):
    for r in ir:
        if r['seed'] == ipil[i % 10]:
            rr = copy.deepcopy(r); rr['seed'] = s; runs.append(rr)
base['runs'] = runs; base['complete'] = True
base['meta'].update(seeds=iseeds, script_sha256=sha(os.path.join(CE, 'indep', 'indep_trust_04.py')),
                    spec_sha256=sha(os.path.join(CE, 'indep', 'SPEC.md')),
                    wrapper=dict(path='indep_runner.py', sha256=sha(os.path.join(CE, 'indep_runner.py'))))
json.dump(base, open(os.path.join(CE, 'indep', 'test700', 'results_indep_04.json'), 'w'), ensure_ascii=False)
env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
print(subprocess.run([sys.executable, 'prereg_hashes.py'], cwd=CE, capture_output=True, text=True, env=env).returncode, 'prereg_hashes')
r = subprocess.run([sys.executable, 'analyze_trust_04.py'], cwd=CE, capture_output=True, text=True, env=env)
print('код анализа MAIN:', r.returncode)
print(r.stderr[-3000:])
for line in r.stdout.splitlines():
    if line.startswith(('сводные', 'чтения', 'реестр', 'C_', 'A15', 'сходимость')):
        print(line[:1500])
a = json.load(open(os.path.join(CE, 'analysis_trust_04.json')))
print('ИТОГ: ветка MAIN исполнена;', 'сводные:', {k: v['outcome'] for k, v in a['summary'].items()})
