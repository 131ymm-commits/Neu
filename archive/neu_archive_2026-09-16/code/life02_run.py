"""LIFE-02 — сорт рождения по времени жизни с калиброванными кромками; ручка настойчивости. По PREREG 2026-09-14 (вечер)."""
import numpy as np, json, sys, time; sys.path.insert(0, '/home/claude')
from life02_lib import *
from scipy.stats import spearmanr
OUT = '/home/claude/life02_results.json'; t0 = time.time(); parts = all_bipartitions(6); res = {}
rng = np.random.default_rng(5051); A = []
for _ in range(1000):
    P = lazy(random_chain(6, rng), 0.8); A.append((P, stationary(P)))
res['A'] = summarize(family_records(A, parts)); print('A ленивые', json.dumps(res['A'], ensure_ascii=False), f'[{time.time()-t0:.0f}s]', flush=True)
rng = np.random.default_rng(5052); B = []
for _ in range(1000):
    P0 = metastable_base(6, 0.02, rng); pi0 = stationary(P0); Pk, thm = knob_chain(P0, pi0, rng); B.append((Pk, stationary(Pk)))
res['B'] = summarize(family_records(B, parts)); print('B токи/метастаб.', json.dumps(res['B'], ensure_ascii=False), f'[{time.time()-t0:.0f}s]', flush=True)
rng = np.random.default_rng(5053); nb = 0
for _ in range(200):
    P = lazy(random_reversible(6, rng), 0.8); pi = stationary(P); rho = spectral_radius(restrict(sym_form(P, pi), pi)); nb += sum(life(P, pi, rho, b, 50) is not None for b in parts)
res['rev_births'] = int(nb); print('обратимые ленивые: рождений', nb, flush=True)
C = {}
for L in (64, 128):
    for s in (0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.6):
        best = None
        for c in (1, 1.5, 2, 2.5, 3, 4):
            P = lifted_local(L, c / L, s); pi = stationary(P); rho = spectral_radius(restrict(sym_form(P, pi), pi))
            if best is None or rho < best[0]: best = (rho, c, P, pi)
        rho, c, P, pi = best; recs = [r for r in (life(P, pi, rho, b, 4000) for b in site_cuts(L)) if r]; ss = sorts(recs)
        C[f'L{L}_s{s}'] = dict(L=L, s=s, c=c, rho=rho, t_rho=-1 / np.log(rho), n_birth=len(recs), fII=(float(np.mean([x == 'II' for x in ss])) if recs else None), tau_med=(float(np.median([r['tau'] for r in recs if r['tau']])) if any(r['tau'] for r in recs) else None), frac_d2pos=(float(np.mean([r['d2'] > 0 for r in recs])) if recs else None))
        print(f"C L={L} s={s}: p*L={c} t_ρ={C[f'L{L}_s{s}']['t_rho']:.1f} рождающих {len(recs)}/{L-1} fII {C[f'L{L}_s{s}']['fII']} τ_med {C[f'L{L}_s{s}']['tau_med']} d₂>0 {C[f'L{L}_s{s}']['frac_d2pos']} [{time.time()-t0:.0f}s]", flush=True)
res['C'] = C
A_, B_ = res['A'], res['B']
def births_at(L, s): return C[f'L{L}_s{s}']['n_birth'] > 0
pg2_ok = all(births_at(L, s) for L in (64, 128) for s in (0, 0.05, 0.1, 0.15, 0.2)) and not any(births_at(L, s) for L in (64, 128) for s in (0.4, 0.6))
fII_low = [C[f'L{L}_s{s}']['fII'] for L in (64, 128) for s in (0, 0.05, 0.1, 0.15, 0.2) if C[f'L{L}_s{s}']['fII'] is not None]
pg2_ok = pg2_ok and all(f >= 0.9 for f in fII_low)
ratioA = (A_['tau_med_d2pos'] / A_['tau_med_d2neg']) if A_.get('tau_med_d2neg') else None
V = dict(K0=nb > 0, PG1=dict(fII_B=B_.get('fII'), fI_B=B_.get('fI'), n_B=B_.get('n'), ok=(B_.get('fII') is not None and B_['fII'] <= 0.15 and B_['fI'] >= 0.7)),
         PG2=dict(ok=pg2_ok, fII_low=fII_low, births_high=[(L, s, C[f'L{L}_s{s}']['n_birth']) for L in (64, 128) for s in (0.4, 0.6)]),
         PG3=dict(ratio=ratioA, ok=(ratioA is not None and ratioA >= 3)), PG4=dict(fI=A_['fI'], fII=A_['fII'], ok=A_['fI'] >= 0.7 and A_['fII'] <= 0.2),
         K1=(B_.get('fII') or 0) >= 0.3, K2=(all(births_at(L, s) for L in (64, 128) for s in (0.4,)) or (bool(fII_low) and min(fII_low) < 0.5)), K3=(ratioA is None or ratioA < 1.5), K4=A_['fII'] >= 0.4)
res['verdict'] = V; json.dump(res, open(OUT, 'w'), default=float); print('ВЕРДИКТ', json.dumps(V, default=float, ensure_ascii=False)); print('ГОТОВО', f'{time.time()-t0:.0f}s')
