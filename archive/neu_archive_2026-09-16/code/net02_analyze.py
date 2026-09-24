"""NET-02 — ранг моды в сети IS против горизонта: разбиения A/B на вложенных горизонтах 2e4 / 5e4 / 1e5 кадров. По PREREG 2026-09-09."""
import numpy as np, json, glob, os, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from net01_analyze_lib import analyze
from mol_levels_lib import microstates
OUT = '/home/claude/net02_results.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}; t0 = time.time()
for fp in sorted(glob.glob('/home/claude/net01L_T*_s*.npz')):
    name = os.path.basename(fp)[7:-4]
    if name in res: continue
    d = np.load(fp); Eis = d['Eis']; D = d['D'].astype(float); ind_all = (Eis <= -44.32).astype(float)
    r = dict(n=int(len(Eis)), n_is=int(len(np.unique(np.round(Eis, 3)))), frac_ico=float(ind_all.mean()), horizons={})
    print(f"{name}: кадров {len(Eis)}, IS {r['n_is']}, доля икосаэдра {r['frac_ico']:.3f}", flush=True)
    for H in (20000, 50000, 100000):
        E = Eis[:H]; X = D[:H]; ind = ind_all[:H]
        labA = np.unique(np.round(E, 3), return_inverse=True)[1]; labB = microstates(X, 100, seed=0)
        rA = analyze(labA, ind, f'A {H}'); rB = analyze(labB, ind, f'B {H}')
        r['horizons'][str(H)] = dict(A=rA, B=rB, n_is=int(len(np.unique(labA))))
    res[name] = r; json.dump(res, open(OUT, 'w'), indent=1, default=float)
reps = [k for k in res]
rA = {H: [res[k]['horizons'][H]['A']['r_ico'] for k in reps] for H in ('20000', '50000', '100000')}; rB = {H: [res[k]['horizons'][H]['B']['r_ico'] for k in reps] for H in ('20000', '50000', '100000')}
mono = sum(1 for k in reps if all((res[k]['horizons'][a]['A']['r_ico'] or 99) >= (res[k]['horizons'][b]['A']['r_ico'] or 99) for a, b in (('20000', '50000'), ('50000', '100000'))))
V = dict(PN2a=dict(ok=sum(x == 1 for x in rA['100000']) >= 5, rA=rA), PN2b=dict(ok=mono >= 5, n_monotone=mono), PN2c=dict(ok=all(x == 1 for H in rB for x in rB[H]), rB=rB),
         K1=dict(hit=sum((x or 99) >= 2 for x in rA['100000']) >= 3), K2=dict(hit=sum(x != 1 for x in rB['100000']) >= 2), K3=dict(hit=float(np.median([x or 99 for x in rA['20000']])) == 1, median_2e4=float(np.median([x or 99 for x in rA['20000']]))))
res['verdicts'] = V; json.dump(res, open(OUT, 'w'), indent=1, default=float)
print('\nранги A по горизонтам:', rA, '\nранги B:', rB, '\n== ВЕРДИКТЫ ==')
for k, v in V.items(): print(k, v)
