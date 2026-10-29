#!/usr/bin/env python3
"""LENSES-3: разброс X1o (AUC agree − single, main_opus) по зёрнам заглушки у ветки A (logit 1 / 0,3 / 1, без потерь) и A3 (то же,
потери 3 % и 2 задачи без записи). Цепочка — та же, что в dry_run.sh: make_stub.py → score02.py metrics → меры score02_lib; интервал —
бутстреп задач B = 2000 (fastlib, семантика проверена). Пишет только в <копия>/seedcheck/.
  python3 seed_spread.py <копия опыта> <папка fastlib> <число зёрен>"""
import json
import os
import subprocess
import sys

import numpy as np

X, FL, NS = sys.argv[1], sys.argv[2], int(sys.argv[3])
sys.path.insert(0, X)
sys.path.insert(0, FL)
import score02_lib as L  # noqa: E402
import fastlib as F  # noqa: E402

out_dir = os.path.join(X, 'seedcheck')
os.makedirs(os.path.join(out_dir, 'evals'), exist_ok=True)
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
res = {}
for br, lost, drop in (('A', '0.0', '0'), ('A3', '0.03', '2')):
    vals = []
    for s in range(NS):
        stub = os.path.join(out_dir, f'stub_{br}_{s}.jsonl')
        subprocess.run([sys.executable, 'dry/make_stub.py', 'main', stub, '1.0', '0.3', '1.0', lost, f'{br}|seed{s}|main_opus', '5', drop, 'logit'],
                       cwd=X, check=True, capture_output=True, env=env)
        st = f'sc_{br}_{s}'
        subprocess.run([sys.executable, 'score02.py', 'metrics', st, 'main', stub, '5', 'seedcheck/evals'], cwd=X, check=True, capture_output=True, env=env)
        J = L.load(st, os.path.join(out_dir, 'evals'))
        tasks = sorted(J)
        M = L.measures(J, tasks)
        d1 = M['agree']['auc2'] - M['single']['auc2']
        H = F.prep(J, tasks)
        W = np.random.default_rng(s).multinomial(len(tasks), np.full(len(tasks), 1 / len(tasks)), size=2000).astype(float)
        lo, hi = F.ci95(F.boot_auc(H['agree'], W) - F.boot_auc(H['single'], W))
        n_calls = sum(len(J[t]['single']) for t in tasks)
        vals.append(dict(seed=s, d1=d1, lo=lo, hi=hi, tasks=len(tasks), single_judgments=n_calls,
                         lev075=float(np.mean([abs(c - 0.75) < 1e-9 for t in tasks for c, _ in J[t]['agree']]))))
    d = np.array([v['d1'] for v in vals])
    res[br] = dict(vals=vals, mean=float(d.mean()), sd=float(d.std(ddof=1)), refuted=sum(v['lo'] > 0 for v in vals))
    print(f"{br}: X1o (agree − single) по {NS} зёрнам — среднее {d.mean():+.4f}, SD {d.std(ddof=1):.4f}, от {d.min():+.4f} до {d.max():+.4f}; "
          f"«опровергнуто» (интервал выше 0) в {res[br]['refuted']} из {NS}; задач {vals[0]['tasks']}; доля уровня 0,75 у agree "
          f"{np.mean([v['lev075'] for v in vals]):.3f}")
diff = res['A3']['mean'] - res['A']['mean']
se = (res['A']['sd'] ** 2 / NS + res['A3']['sd'] ** 2 / NS) ** 0.5
print(f'A3 − A: {diff:+.4f} (SE {se:.4f})')
json.dump(res, open(os.path.join(out_dir, 'seed_spread.json'), 'w'), indent=1)
