"""LIFE-02 пилот семейства C (сид 5063): лифтированный путь с ручкой детерминизма s; p = c/L, c ∈ {1,2,3,4}; L = 32; τ и d₂ у среднего разреза и всех разрезов."""
import numpy as np, json, sys, time; sys.path.insert(0, '/home/claude')
from life02_lib import *
t0 = time.time(); L = 32; out = {}
for s in (0.0, 0.1, 0.3, 0.6, 1.0):
    rng = np.random.default_rng(5063); rows = []
    for rep in range(8):
        best = None
        for c in (1, 2, 3, 4):
            P = lifted_mixed(L, c / L, s, rng); pi = stationary(P); rho = spectral_radius(restrict(sym_form(P, pi), pi))
            if best is None or rho < best[0]: best = (rho, c, P, pi)
        rho, c, P, pi = best; recs = [r for r in (life(P, pi, rho, b, 2000) for b in site_cuts(L)) if r]
        mid = life(P, pi, rho, site_cuts(L)[L // 2 - 1], 2000)
        rows.append(dict(c=c, rho=rho, t_rho=-1 / np.log(rho), n_birth=len(recs), mid=mid, fII=(np.mean([x == 'II' for x in sorts(recs)]) if recs else None)))
    out[f's{s}'] = rows
    print(f"s={s}: p*L медиана {np.median([r['c'] for r in rows])}, t_ρ медиана {np.median([r['t_rho'] for r in rows]):.1f}, рождающих разрезов {[r['n_birth'] for r in rows]}, mid: τ {[round(r['mid']['tau'], 2) if r['mid'] and r['mid']['tau'] else None for r in rows]}, d₂>0 {[bool(r['mid']['d2'] > 0) if r['mid'] else None for r in rows]}, fII {[round(r['fII'], 2) if r['fII'] is not None else None for r in rows]}", flush=True)
json.dump(out, open('/home/claude/life02_pilot_c.json', 'w'), default=float); print('готово', f'{time.time()-t0:.0f}s')
