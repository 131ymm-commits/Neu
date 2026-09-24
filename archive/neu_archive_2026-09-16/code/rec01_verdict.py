"""REC-01 — вердикты по PREREG (2026-09-05)."""
import json, numpy as np
from scipy.stats import kstest
d = json.load(open('/home/claude/rec01_lj.json')); s = json.load(open('/home/claude/rec01b_sinai.json')); dip = json.load(open('/home/claude/rec01_dip.json'))
def sets(Tq, liq=False):
    return [v for k, v in d.items() if ((k.startswith(f'Q{Tq}_') and 'e250' not in k and 'tol' not in k) if not liq else k.startswith('LIQ'))]
summary = {}
for Tq in (0.1, 0.14, 0.2, 0.24):
    ks = sets(Tq); kg = [v['k_gs'] for v in ks]; cens = sum(1 for x in kg if x is None); kgv = [x for x in kg if x is not None]
    # цензурированные: попытка была, но основное состояние не достигнуто — k_gs ≥ n_rec (все рекорды — промежуточные); для медианы берём n_rec как нижнюю границу
    kg_lb = [x if x is not None else v['n_rec'] for x, v in zip(kg, ks)]
    pi = [x for v in ks for x in v['phi_int']]; tg = [v['t_gs'] for v in ks if v['t_gs']]
    D = np.concatenate([np.diff(np.log(np.array(v['rec_t'], float)))[1:] for v in ks if len(v['rec_t']) > 3]) if any(len(v['rec_t']) > 3 for v in ks) else np.array([])
    summary[Tq] = dict(n=len(ks), k_gs=kgv, censored=cens, k_gs_lb=kg_lb, median_k_lb=float(np.median(kg_lb)), n_k2=int(sum(1 for x in kg_lb if x >= 2)), n_k_le1=int(sum(1 for x in kg_lb if x <= 1)),
                       phi_int_median=(float(np.median(pi)) if pi else None), n_phi=len(pi), t_gs_median=(float(np.median(tg)) if tg else None),
                       D_n=int(len(D)), D_mean=(float(D.mean()) if len(D) else None), D_cv=(float(D.std() / D.mean()) if len(D) > 1 else None),
                       ks_p=(float(kstest(D, 'expon', args=(0, D.mean())).pvalue) if len(D) > 5 else None))
liq = sets(0.36, liq=True); pi_l = [x for v in liq for x in v['phi_int']]
Dl = np.concatenate([np.diff(np.log(np.array(v['rec_t'], float)))[1:] for v in liq if len(v['rec_t']) > 3])
summary['liq'] = dict(n=len(liq), n_rec=[v['n_rec'] for v in liq], phi_int_median=float(np.median(pi_l)), D_n=int(len(Dl)), D_mean=float(Dl.mean()), D_cv=float(Dl.std() / Dl.mean()),
                      ks_p=float(kstest(Dl, 'expon', args=(0, Dl.mean())).pvalue), frac_gs=[round(v['frac_gs'], 2) for v in liq])
# линейно-пуассоновский контроль для Δ_k (те же числа событий на [50, 2e5])
rng = np.random.default_rng(1); Dlin = np.concatenate([np.diff(np.log(np.sort(rng.uniform(50, 2e5, len(v['rec_t'])))))[1:] for v in sets(0.2) + liq if len(v['rec_t']) > 3])
summary['linear_control_ks_p'] = float(kstest(Dlin, 'expon', args=(0, Dlin.mean())).pvalue)
for Tq in (0.1, 0.14, 0.2, 0.24):
    v = summary[Tq]; print(f"T_q={Tq}: k_gs (нижн. гр., цензур. {v['censored']}) = {v['k_gs_lb']} медиана {v['median_k_lb']}; k≥2: {v['n_k2']}/{v['n']}; k≤1: {v['n_k_le1']}; φ_int медиана {v['phi_int_median']} (n {v['n_phi']}); t_gs медиана {v['t_gs_median']}; Δ_k n {v['D_n']} mean {v['D_mean']} CV {v['D_cv']} KS p {v['ks_p']}")
print('жидкость 0.36:', {k: summary['liq'][k] for k in ('n_rec', 'phi_int_median', 'D_n', 'D_cv', 'ks_p', 'frac_gs')}); print('лин. контроль KS p:', summary['linear_control_ks_p'])
# вердикты
q1 = summary[0.2]['n_k2'] >= 10; k1 = summary[0.2]['n_k_le1'] >= 14
med = [summary[T]['median_k_lb'] for T in (0.1, 0.14, 0.2, 0.24)]; q1b = all(med[i] >= med[i + 1] for i in range(3)); k1b = med[0] < med[3]
q2 = all(summary[T]['phi_int_median'] >= 0.5 for T in (0.1, 0.14, 0.2)) and summary['liq']['phi_int_median'] <= 0.3; k2 = summary[0.2]['phi_int_median'] < 0.3
q3 = (summary[0.2]['ks_p'] or 0) > 0.05 and summary['liq']['ks_p'] > 0.05 and summary['linear_control_ks_p'] < 0.01
sin = {k: (v['phi_trap_median'], v['frac_last_decade'], v['r2']) for k, v in s.items()}
q4 = s['th0.05']['phi_trap_median'] >= 0.5 and s['th0.05']['frac_last_decade'] >= 0.5 and s['th0.15']['phi_trap_median'] <= 0.3 and s['th0.15']['frac_last_decade'] <= 0.2 and s['th0.05']['r2'] >= 0.9
k4 = s['th0.05']['phi_trap_median'] < 0.3
n_dip = [v['n_rec'] for v in dip.values()]; last = [v['last_rec_frac'] for v in dip.values()]
q5 = sum(1 for x in n_dip if x <= 3) >= 8 and sum(1 for x in last if x <= 0.2) >= 8; k3 = sum(1 for x in last if x > 0.2) >= 5
V = dict(PQ1=dict(ok=q1, K1=k1), PQ1b=dict(ok=q1b, K1b=k1b, medians=med), PQ2=dict(ok=q2, K2=k2), PQ3=dict(ok=q3), PQ4=dict(ok=q4, K4=k4, sinai=sin), PQ5=dict(ok=q5, K3=k3))
summary['verdicts'] = V; json.dump(summary, open('/home/claude/rec01_summary.json', 'w'), indent=1, default=float)
print('\n== ВЕРДИКТЫ ==')
for k, v in V.items(): print(k, v)
