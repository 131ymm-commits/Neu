"""LIFE-02 пилот семейства C (локальный шум): L = 32, s ∈ {0…1}, p = c/L, c ∈ {1,2,3,4,6}; τ, d₂, доля сорта II у рождающих разрезов."""
import numpy as np, json, sys, time; sys.path.insert(0, '/home/claude')
from life02_lib import *
t0 = time.time(); L = 32; out = {}
for s in (0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0):
    best = None
    for c in (1, 2, 3, 4, 6):
        P = lifted_local(L, c / L, s); pi = stationary(P); rho = spectral_radius(restrict(sym_form(P, pi), pi))
        if best is None or rho < best[0]: best = (rho, c, P, pi)
    rho, c, P, pi = best; recs = [r for r in (life(P, pi, rho, b, 3000) for b in site_cuts(L)) if r]; mid = life(P, pi, rho, site_cuts(L)[L // 2 - 1], 3000)
    out[f's{s}'] = dict(c=c, rho=rho, t_rho=-1 / np.log(rho), n_birth=len(recs), mid=mid, fII=(float(np.mean([x == 'II' for x in sorts(recs)])) if recs else None), tau_med=(float(np.median([r['tau'] for r in recs if r['tau']])) if recs and any(r['tau'] for r in recs) else None))
    print(f"s={s}: p*L={c} ρ={rho:.4f} t_ρ={-1/np.log(rho):.1f} рождающих {len(recs)}/{L-1} | mid: {('τ %.2f d₂ %.1e' % (mid['tau'], mid['d2'])) if mid and mid['tau'] else mid} | fII {out[f's{s}']['fII']} τ_med {out[f's{s}']['tau_med']}", flush=True)
json.dump(out, open('/home/claude/life02_pilot_c2.json', 'w'), default=float); print('готово', f'{time.time()-t0:.0f}s')
