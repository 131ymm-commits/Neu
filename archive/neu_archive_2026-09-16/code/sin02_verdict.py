"""SIN-02 — вердикты по PREREG + описательно: фактор Фано n(10⁸) по ландшафтам (лог-Пуассон с общим α → var/mean ≈ 1), Δ_k по k ≥ 2 и по k ≥ 3."""
import json, numpy as np
from scipy.stats import kstest, spearmanr
r = json.load(open('/home/claude/sin02_results.json')); V = {}; out = {}
for key, d in sorted(r.items(), key=lambda kv: kv[1]['theta']):
    th = d['theta']; REC = d['rec_times']; nrec = np.array([len(x) for x in REC], float)
    fano = float(nrec.var() / max(1e-9, nrec.mean()))
    D2 = np.concatenate([np.diff(np.log(np.array(x, float)))[1:] for x in REC if len(x) > 2]) if any(len(x) > 2 for x in REC) else np.array([])
    D3 = np.concatenate([np.diff(np.log(np.array(x, float)))[2:] for x in REC if len(x) > 3]) if any(len(x) > 3 for x in REC) else np.array([])
    # нормировка на ландшафт: Δ_k / среднее Δ ходока (только ходоки с ≥ 3 интервалами) — убирает разброс α между ландшафтами
    Dn = np.concatenate([(lambda dd: dd / dd.mean())(np.diff(np.log(np.array(x, float)))[1:]) for x in REC if len(x) > 4]) if any(len(x) > 4 for x in REC) else np.array([])
    ks2 = float(kstest(D2, 'expon', args=(0, D2.mean())).pvalue) if len(D2) > 10 else None
    ksn = float(kstest(Dn, 'expon', args=(0, Dn.mean())).pvalue) if len(Dn) > 10 else None
    out[key] = dict(theta=th, T=d['T'], h_over_T=d['h'] / d['T'], n_valleys=d['n_valleys_median'], n_rec_median=d['n_rec_median'], n_rec_mean=d['n_rec_mean'], alpha=d['alpha'], alpha_ci=d['alpha_ci'], r2=d['r2'], alpha_lo=d['alpha_lo'], alpha_hi=d['alpha_hi'],
                    late_over_early=(d['alpha_hi'] / d['alpha_lo'] if d['alpha_lo'] else None), D_n=d['D_n'], D_cv=d['D_cv'], ks_p=d['ks_p'], ks_linear=d['ks_linear_control'], fano=fano,
                    D3_n=int(len(D3)), D3_cv=(float(D3.std() / D3.mean()) if len(D3) > 5 else None), Dn_n=int(len(Dn)), Dn_cv=(float(Dn.std() / Dn.mean()) if len(Dn) > 5 else None), ks_norm=ksn,
                    phi_trap_median=d['phi_trap_median'], frac_reach_global=d['frac_reach_global'])
    o = out[key]
    print(f"θ={th}: h/T {o['h_over_T']:.2f} | долин {o['n_valleys']:.0f} рекордов мед {o['n_rec_median']:.0f} (ср {o['n_rec_mean']:.1f}) | α {o['alpha']:.3f} [{o['alpha_ci'][0]:.3f},{o['alpha_ci'][1]:.3f}] R² {o['r2']:.3f} поздний/ранний {o['late_over_early']:.2f} | "
          f"Δ_k (k≥2) n {o['D_n']} CV {o['D_cv']:.2f} KS {o['ks_p']:.2g} лин {o['ks_linear']:.2g} | k≥3 n {o['D3_n']} CV {o['D3_cv']} | нормир. n {o['Dn_n']} CV {o['Dn_cv']} KS {o['ks_norm']} | Фано {fano:.2f} | φ_trap {o['phi_trap_median']:.2f} | глоб {o['frac_reach_global']:.2f}")
g = lambda th: out.get(f'th{th}')
a, b, c, dgn = g(0.05), g(0.1), g(0.15), g(1.0)
V['PN1'] = dict(ok=bool(a and b and a['r2'] >= 0.9 and b['r2'] >= 0.9 and 0.7 <= a['late_over_early'] <= 1.3 and 0.7 <= b['late_over_early'] <= 1.3), r2=[x['r2'] if x else None for x in (a, b)], late_over_early=[x['late_over_early'] if x else None for x in (a, b)])
V['PN2'] = dict(ok=bool(a and a['ks_p'] is not None and a['ks_p'] >= 0.01 and 0.7 <= a['D_cv'] <= 1.3 and a['ks_linear'] < 0.01), ks=a['ks_p'] if a else None, cv=a['D_cv'] if a else None, ks_linear=a['ks_linear'] if a else None,
               control_powerless=bool(a and not (a['ks_linear'] < 0.01)))
phis = [x['phi_trap_median'] for x in (a, b, c) if x]
V['PN3'] = dict(ok=bool(a and a['phi_trap_median'] >= 0.5 and len(phis) == 3 and phis[0] > phis[1] > phis[2]), phi=phis)
V['PN4'] = dict(ok=bool(dgn and dgn['late_over_early'] is not None and dgn['late_over_early'] < 0.3), late_over_early=(dgn['late_over_early'] if dgn else None))
V['K1'] = dict(hit=bool(a and (a['r2'] < 0.8 or a['late_over_early'] < 0.5)))
V['K2'] = dict(hit=bool(a and a['ks_p'] is not None and a['ks_p'] < 0.01 and 0.7 <= a['D_cv'] <= 1.3))
V['K3'] = dict(hit=bool(a and a['phi_trap_median'] < 0.3))
json.dump(dict(cells=out, verdicts=V), open('/home/claude/sin02_summary.json', 'w'), indent=1)
print('\n== ВЕРДИКТЫ ==')
for k, v in V.items(): print(k, v)
