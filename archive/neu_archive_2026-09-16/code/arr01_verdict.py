"""ARR-01 — вердикты: τ̂_att(T) по экспоненциальному правдоподобию с цензурой, Аррениус ln τ̂ ~ 1/T, LOO по T, сходимость 10/20, линейная против квадратичной (AIC)."""
import json, numpy as np, glob
r = {}
for p in sorted(glob.glob('/home/claude/arr01_results_*.json')): r.update(json.load(open(p)))
rows = []
for key in sorted(r):
    d = r[key]; T = d['T']; tg = np.array(d['t_gs'], float); c = np.array(d['cens'], bool); n = len(tg)
    if n == 0: continue
    n_esc = int((~c).sum()); tau = tg.sum() / max(1, n_esc); se = 1 / np.sqrt(max(1, n_esc))
    tau10 = tg[:10].sum() / max(1, (~c[:10]).sum())
    tx = np.array(d['t_exit'], float); rows.append(dict(T=T, n=n, n_esc=n_esc, cens=float(c.mean()), tau=tau, ln_tau=float(np.log(tau)), se_ln=se, tau10=tau10, t_exit_median=float(np.median(tx)), t_gs_median=float(np.median(tg)),
                                                       direct=float(np.mean([e is not None and e < -44.3 for e in d['E_first_exit']]))))
    print(f"T={T:.2f} n={n:2d} побегов {n_esc:2d} цензура {c.mean():.2f} | τ̂_att {tau:9.0f} (по 10: {tau10:9.0f}) | медиана t_gs {np.median(tg):8.0f} | первый выход из бассейна медиана {np.median(tx):8.0f}, прямо в икосаэдр {rows[-1]['direct']:.2f}")
fit_rows = [x for x in rows if x['T'] < 0.3 and x['n_esc'] >= 3]
X = np.array([1 / x['T'] for x in fit_rows]); Y = np.array([x['ln_tau'] for x in fit_rows]); W = np.array([1 / x['se_ln'] ** 2 for x in fit_rows])
def wfit(X, Y, W, deg=1):
    c = np.polyfit(X, Y, deg, w=np.sqrt(W)); pred = np.polyval(c, X); rss = float(np.sum(W * (Y - pred) ** 2)); return c, pred, rss
c1, p1, rss1 = wfit(X, Y, W); c2, p2, rss2 = wfit(X, Y, W, 2)
r2 = float(1 - np.sum((Y - p1) ** 2) / max(1e-12, np.sum((Y - Y.mean()) ** 2)))
n = len(X); aic1 = n * np.log(rss1 / n) + 2 * 2; aic2 = n * np.log(rss2 / n) + 2 * 3
slope = float(c1[0]); loo = [float(wfit(np.delete(X, i), np.delete(Y, i), np.delete(W, i))[0][0]) for i in range(n)]
slope10 = float(np.polyfit(X, np.log([x['tau10'] for x in fit_rows]), 1)[0])
t12 = next((x['tau'] for x in rows if abs(x['T'] - 0.12) < 1e-6), None); t20 = next((x['tau'] for x in rows if abs(x['T'] - 0.20) < 1e-6), None)
print(f"\nАррениус по {n} точкам (T ≤ 0.20, ≥ 3 побегов): наклон ΔE_fit = {slope:.3f} ε (NEB 1.04), пересечение ln τ₀ = {c1[1]:.2f} (τ₀ = {np.exp(c1[1]):.0f} шагов), R² = {r2:.3f}; LOO наклоны {np.round(loo, 2)}; по 10 репликам {slope10:.3f}; AIC лин {aic1:.1f} квадр {aic2:.1f} (кривизна {c2[0]:+.3f})")
if t12 and t20: print(f"τ(0.12)/τ(0.20) = {t12 / t20:.1f}")
V = dict(PAR1=dict(ok=bool(r2 >= 0.9 and 0.73 <= slope <= 1.35 and n >= 5), slope=slope, r2=r2, n=n, tau0=float(np.exp(c1[1]))), PAR2=dict(ok=bool(not (0.73 <= slope <= 1.35)), slope=slope),
         PAR3=dict(ok=bool(t12 and t20 and t12 / t20 >= 10), ratio=(float(t12 / t20) if (t12 and t20) else None)),
         K1=dict(hit=bool(slope <= 0.3 or r2 < 0.7)), K2=dict(hit=bool(t12 and t20 and t12 <= t20)), K3=dict(hit=bool(all(x['cens'] > 0.5 for x in rows if 0.14 <= x['T'] < 0.3))),
         LOO_ok=bool(all(abs(l - slope) <= 0.3 * abs(slope) for l in loo)), conv10_ok=bool(abs(slope10 - slope) <= 0.2 * abs(slope)), aic_lin_minus_quad=float(aic1 - aic2), curvature=float(c2[0]))
json.dump(dict(rows=rows, verdicts=V), open('/home/claude/arr01_summary.json', 'w'), indent=1)
print('\n== ВЕРДИКТЫ ==')
for k, v in V.items(): print(k, v)
