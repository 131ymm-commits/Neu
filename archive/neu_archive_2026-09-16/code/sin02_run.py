"""SIN-02 — синаевская нуль-вселенная в режиме многих квейков: L = 1024, горизонт 1e8 шагов, h-долины с ФИКСИРОВАННЫМ h = 4 (единицы
ландшафта, не T), 200 ландшафтов на θ; рекорды = первое попадание в h-долину с дном ниже всех прежних; n(t), Δ_k = ln t_{k+1} − ln t_k,
захват φ_trap, достижение глобальной долины. По PREREG 2026-09-08. Запуск: python3 sin02_run.py [theta ...]"""
import numpy as np, json, os, sys, time
from numba import njit
from scipy.stats import kstest
sys.path.insert(0, '/home/claude')
OUT = '/home/claude/sin02_results.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}
L = 1024; NLAND = 200; STEPS = 100_000_000; H = 4.0; MAXREC = 64
THETAS = [float(a) for a in sys.argv[1:]] or [0.05, 0.1, 0.15, 1.0]
GRID = np.unique(np.logspace(1, 8, 71).astype(np.int64))

from sin02_lib import walk, h_valleys

t0 = time.time()
for th in THETAS:
    key = f'th{th}'
    if key in res: continue
    rng = np.random.default_rng(3000 + int(th * 1000)); T = th * np.sqrt(L)
    U = np.cumsum(rng.standard_normal((NLAND, L)), axis=1); U -= U.min(1, keepdims=True)
    REC = []; NAT = []; PHI = []; GM = []; NV = []; DEPTH = []
    for i in range(NLAND):
        v, b = h_valleys(U[i], H); NV.append(len(b))
        rt, rd, n_at, phi, gt = walk(U[i], v.astype(np.int64), b.astype(np.float64), T, STEPS, 5000 + i + int(th * 1000), GRID, MAXREC)
        REC.append([int(x) for x in rt]); DEPTH.append([float(x) for x in rd]); NAT.append(n_at); PHI.append(phi); GM.append(int(gt))
        if i % 50 == 0: print(f'θ={th} ландшафт {i}: рекордов {len(rt)}, φ_trap {phi:.2f}, глобальная долина при {gt} [{time.time()-t0:.0f}s]', flush=True)
    NAT = np.array(NAT, float); mean_n = NAT.mean(0); ok = GRID >= 1000
    a, b = np.polyfit(np.log(GRID[ok]), mean_n[ok], 1); pred = a * np.log(GRID[ok]) + b
    r2 = float(1 - np.sum((mean_n[ok] - pred) ** 2) / max(1e-12, np.sum((mean_n[ok] - mean_n[ok].mean()) ** 2)))
    lo = (GRID >= 1000) & (GRID <= 1e5); hi = GRID >= 1e5
    a_lo = float(np.polyfit(np.log(GRID[lo]), mean_n[lo], 1)[0]); a_hi = float(np.polyfit(np.log(GRID[hi]), mean_n[hi], 1)[0])
    D = np.concatenate([np.diff(np.log(np.array(r, float)))[1:] for r in REC if len(r) > 2]) if any(len(r) > 2 for r in REC) else np.array([])
    ks = float(kstest(D, 'expon', args=(0, D.mean())).pvalue) if len(D) > 10 else None
    Dl = np.concatenate([np.diff(np.log(np.sort(rng.uniform(1, STEPS, len(r)))))[1:] for r in REC if len(r) > 2]) if len(D) else np.array([])
    ksl = float(kstest(Dl, 'expon', args=(0, Dl.mean())).pvalue) if len(Dl) > 10 else None
    boot = [np.polyfit(np.log(GRID[ok]), NAT[rng.integers(0, NLAND, NLAND)].mean(0)[ok], 1)[0] for _ in range(200)]
    res[key] = dict(theta=th, T=float(T), h=H, n_valleys_median=float(np.median(NV)), n_rec_median=float(np.median([len(r) for r in REC])), n_rec_mean=float(np.mean([len(r) for r in REC])),
                    alpha=float(a), alpha_ci=[float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))], r2=r2, alpha_lo=a_lo, alpha_hi=a_hi,
                    D_n=int(len(D)), D_mean=(float(D.mean()) if len(D) else None), D_cv=(float(D.std() / D.mean()) if len(D) else None), ks_p=ks, ks_linear_control=ksl,
                    phi_trap_median=float(np.median(PHI)), phi_trap_q=[float(np.quantile(PHI, 0.25)), float(np.quantile(PHI, 0.75))],
                    frac_reach_global=float(np.mean([g > 0 for g in GM])), t_global_median=(float(np.median([g for g in GM if g > 0])) if any(g > 0 for g in GM) else None),
                    grid=[int(g) for g in GRID], mean_n=[float(v) for v in mean_n], rec_times=REC, rec_depths=DEPTH, phi_trap=[float(p) for p in PHI], t_global=GM)
    json.dump(res, open(OUT, 'w'), indent=1)
    print(f"== θ={th} (T={T:.2f}, h/T={H/T:.2f}): долин {np.median(NV):.0f}; рекордов мед {np.median([len(r) for r in REC]):.0f}; n(t) ~ {a:.2f} ln t (R² {r2:.3f}; ранний/поздний наклон {a_lo:.2f}/{a_hi:.2f}); "
          f"Δ_k n {len(D)} CV {res[key]['D_cv']} KS p {ks} | лин.контроль KS p {ksl}; φ_trap мед {np.median(PHI):.2f}; глобальная долина достигнута {np.mean([g > 0 for g in GM]):.2f} [{time.time()-t0:.0f}s]", flush=True)
print('готово', time.time() - t0)
