"""LIFE-02 пилот (сиды 5061/5062, ДРУГИЕ, чем в прогоне): распределения t_ρ и τ по семействам A (ленивые случайные, a = 0.8) и B (токи на метастабильной базе, eps = 0.02) — для калибровки кромок."""
import numpy as np, json, sys, time; sys.path.insert(0, '/home/claude')
from life02_lib import *
t0 = time.time(); parts = all_bipartitions(6); out = {}
rng = np.random.default_rng(5061); A = []
for _ in range(200):
    P = lazy(random_chain(6, rng), 0.8); A.append((P, stationary(P)))
out['A_lazy'] = summarize(family_records(A, parts)); print('A ленивые (пилот)', json.dumps(out['A_lazy'], ensure_ascii=False), f'[{time.time()-t0:.0f}s]', flush=True)
rng = np.random.default_rng(5062); B = []; thms = []
for _ in range(200):
    P0 = metastable_base(6, 0.02, rng); pi0 = stationary(P0); Pk, thm = knob_chain(P0, pi0, rng); thms.append(thm); B.append((Pk, stationary(Pk)))
out['B_meta'] = summarize(family_records(B, parts)); out['B_meta']['theta_max_median'] = float(np.median(thms)); print('B токи на метастабильной базе (пилот)', json.dumps(out['B_meta'], ensure_ascii=False), f'[{time.time()-t0:.0f}s]', flush=True)
json.dump(out, open('/home/claude/life02_pilot.json', 'w'), default=float)
