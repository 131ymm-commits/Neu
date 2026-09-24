"""DUST-02 — NGRIP 20 лет, 11.62–32.44 ka: R = t1(2D)/t1(1D), выживание на отложенной половине, шумовой контроль, суррогаты, сиды; окна W и Wg. По PREREG 2026-09-09."""
import numpy as np, json, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from dust01_run_lib import load, std, embed, test, heldout, surrogate
OUT = '/home/claude/dust02_results.json'; res = {}; t0 = time.time(); K = 20
a_all, d_all, lc_all = load('/home/claude/ngrip2d/ngrip_ca_20yr_full.txt')
for win, (lo, hi) in (('W', (11600, 32500)), ('Wg', (23000, 32500))):
    m = (a_all >= lo) & (a_all <= hi); a, d, lc = a_all[m], d_all[m], lc_all[m]; n = len(a); r = dict(n=n, age_min=float(a.min()), age_max=float(a.max()))
    F1 = std(embed(d, 2)); F2 = std(np.column_stack([d, lc]))
    t1d = test(F1, k=K); t2d = test(F2, k=K)
    for name, t in (('1D_m2', t1d), ('2D_d18O_lnCa', t2d)):
        r[name] = {k: v for k, v in t.items() if k not in ('lab', 'msm', 'c')}
        print(f"{win} {name:14s} n={t['n']} сост {t['n_states']} | ITS {np.round(t['its'][:5], 2)} | ζ {None if t['zeta'] is None else round(t['zeta'], 2)} {None if not t['zeta_q'] else np.round(t['zeta_q'], 2)} P_L {t['PL']:.2f} → {t['dec']} [{time.time()-t0:.0f}s]", flush=True)
    r['R'] = t2d['t1'] / t1d['t1']; r['R_seeds'] = [test(F2, k=K, seed=s)['t1'] / test(F1, k=K, seed=s)['t1'] for s in (1, 2, 3)]
    rng = np.random.default_rng(0); Rn = []; Rs = []
    for s in range(10):
        Fn = std(np.column_stack([d, rng.normal(size=n)])); Rn.append(test(Fn, k=K)['t1'] / t1d['t1'])
        ds, cs = surrogate(std(d), rng), surrogate(std(lc), rng); Rs.append(test(std(np.column_stack([ds, cs])), k=K)['t1'] / test(std(embed(ds, 2)), k=K)['t1'])
    r['R_noise_q'] = [float(np.quantile(Rn, q)) for q in (0.1, 0.5, 0.9)]; r['R_surr_median'] = float(np.median(Rs)); r['R_surr'] = [float(x) for x in Rs]
    r['heldout_2D'] = heldout(F2, k=K); r['heldout_1D'] = heldout(F1, k=K)
    print(f"{win}: R = {r['R']:.2f} (сиды {np.round(r['R_seeds'], 2)}) | шум R q10/50/90 {np.round(r['R_noise_q'], 2)} | суррогаты R медиана {r['R_surr_median']:.2f} | отложенная 2D {r['heldout_2D']['ratio']:.2f} (t1 {r['heldout_2D']['t1_train']:.1f} → {r['heldout_2D']['t1_test']:.1f}) 1D {r['heldout_1D']['ratio']:.2f}", flush=True)
    res[win] = r; json.dump(res, open(OUT, 'w'), indent=1, default=float)
W, Wg = res['W'], res['Wg']
V = dict(PD2a=dict(ok=bool(W['R'] >= 1.5 and 0.5 <= W['heldout_2D']['ratio'] <= 2), R=W['R'], surv=W['heldout_2D']['ratio']), PD2b=dict(ok=bool(15 <= W['2D_d18O_lnCa']['t1'] <= 60), t1=W['2D_d18O_lnCa']['t1']),
         PD2c=dict(ok=bool(Wg['R'] >= 1.5), R=Wg['R']), PD2d=dict(ok=bool(W['R_surr_median'] <= 1.2), R_surr=W['R_surr_median']),
         K1=dict(hit=bool(W['R'] <= 1.2)), K2=dict(hit=bool(W['R'] >= 1.5 and not (0.5 <= W['heldout_2D']['ratio'] <= 2))), K3=dict(hit=bool(W['R_noise_q'][2] >= 1.5)), K4=dict(hit=bool(W['R'] >= 1.5 and Wg['R'] <= 1.2)))
res['verdicts'] = V; json.dump(res, open(OUT, 'w'), indent=1, default=float)
print('\n== ВЕРДИКТЫ ==')
for k, v in V.items(): print(k, v)
