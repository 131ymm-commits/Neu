"""VIRT-01 — прогон по PREREG (2026-09-14, вечер). (A) V ∈ {0, 0.6, 0.7, 0.8, 0.9, 0.95, 1.2, 1.5}, N = 6000, τ = 1, n ≤ 2000.
(B) Δ ∈ {20, 40}, γ = 2, Ω = 1, τ = 0.2/Ω_R, r = γ_g/2Ω_R по сетке; Λ-система и двухуровневый контроль. Числа — в virt01_results.json."""
import numpy as np, json, time, warnings
from scipy.stats import spearmanr
from virt01_lib import *
warnings.filterwarnings('ignore'); t0 = time.time(); OUT = '/home/claude/virt01_results.json'; res = dict(A={}, B={}, verdict={})
# ---------------- (A)
N, nmax = 6000, 2000
for V in (0.0, 0.6, 0.7, 0.8, 0.9, 0.95, 1.2, 1.5):
    w, a0, C = chain_corr(N, V, nmax); nc, eps = crossover(C); D = memory(C); E = implied_energy(C)
    a = -1 / (1 - V) if V != 1 else None; rho = float(np.exp(-w[0])); Om = float(C[1] / C[0])
    res['A'][str(V)] = dict(V=V, a=a, a2=(a * a if a else None), nc=nc, ratio=(nc / (a * a) if (nc and a and V < 1) else None), Omega=Om, rho=rho, born=bool(Om > rho + 1e-9),
                            Dmin=float(D[1:].min()), E_last=float(E[-1]), E_b=(float(-(V + 1 / V) + 2) if V > 1 else None),
                            eps_at=[float(eps[k]) for k in (1, 3, 9, 30, 99, 299, 999, 1999)])
    r = res['A'][str(V)]; print(f"A V={V}: n_c={nc} a²={r['a2']} n_c/a²={r['ratio']} Ω={Om:.5f} ρ={rho:.6f} рожд={r['born']} minD={r['Dmin']:.1e} E(2000)={r['E_last']:.5f} E_b={r['E_b']} ε: {np.round(r['eps_at'],3)} [{time.time()-t0:.0f}s]", flush=True)
Vs = [0.6, 0.7, 0.8, 0.9, 0.95]; ratios = [res['A'][str(V)]['ratio'] for V in Vs]; undefined = [V for V in Vs if res['A'][str(V)]['nc'] is None]
# по букве PREREG: 5 точек; если n_c не определён (ε(n) не опускается ниже 1 — нет режима 1/2 при малых a), прогноз P-Q7 не вычислим по кромке
ok5 = len(undefined) == 0
Vd = [V for V in Vs if res['A'][str(V)]['nc'] is not None and res['A'][str(V)]['nc'] > 1]; aa = [abs(res['A'][str(V)]['a']) for V in Vd]; ncs = [res['A'][str(V)]['nc'] for V in Vd]; rd = [res['A'][str(V)]['ratio'] for V in Vd]
slope = float(np.polyfit(np.log(aa), np.log(ncs), 1)[0]) if len(Vd) >= 2 else None; sp = float(spearmanr(aa, rd)[0]) if len(Vd) >= 3 else None
r09 = res['A']['0.9']['ratio']; r095 = res['A']['0.95']['ratio']
res['verdict']['PQ7'] = dict(ratios=dict(zip(map(str, Vs), ratios)), undefined_V=undefined, points_used=Vd, spearman=sp, slope=slope,
                             edges_ok=bool(r09 and r095 and 0.50 <= r09 <= 0.66 and 0.55 <= r095 <= 0.70), slope_ok=bool(slope and 1.9 <= slope <= 2.4),
                             ok=bool(ok5 and sp == 1.0 and r09 and r095 and 0.50 <= r09 <= 0.66 and 0.55 <= r095 <= 0.70 and slope and 1.9 <= slope <= 2.4))
res['verdict']['K7'] = bool(slope is not None and (slope < 1.5 or slope > 2.7))
res['verdict']['PQ8'] = dict(births=int(sum(res['A'][k]['born'] for k in res['A'])), Dmin=float(min(res['A'][k]['Dmin'] for k in res['A'])),
                             bound_dev=[abs(res['A'][k]['E_last'] - res['A'][k]['E_b']) for k in ('1.2', '1.5')])
res['verdict']['PQ8']['ok'] = bool(res['verdict']['PQ8']['births'] == 0 and res['verdict']['PQ8']['Dmin'] >= -1e-12 and all(d < 1e-4 for d in res['verdict']['PQ8']['bound_dev']))
print('A вердикт:', json.dumps({k: res['verdict'][k] for k in ('PQ7', 'K7', 'PQ8')}, ensure_ascii=False, default=float), flush=True)
# ---------------- (B)
gamma, Omega = 2.0, 1.0; rs = [0, 0.1, 0.2, 0.5, 0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.2, 1.5, 2, 3, 5]
for Delta in (20.0, 40.0):
    OmR = Omega ** 2 / (2 * Delta); Rsc = gamma * Omega ** 2 / (4 * Delta ** 2); tau = 0.2 / OmR; rows = []
    for r in rs:
        gg = r * 2 * OmR; Ls = lambda_system(Omega, Delta, gamma, gg); blocks = [[0], [2], [1]] if r > 0 else [[0], [2]]
        A = description_analysis(Ls, 3, tau, blocks); Lc = two_level_control(OmR, Rsc, Rsc + gg); Cc = description_analysis(Lc, 2, tau, [[0]])
        b0 = A['blocks']['[0]']; b2 = A['blocks']['[2]']; b1 = A['blocks'].get('[1]'); c0 = Cc['blocks']['[0]']
        row = dict(r=r, gamma_g=gg, gap=A['gap'], rho=A['rho'], t_rho=A['t_rho'], n_max=A['n_max'], pi=A['pi'], R=b0['R'], born=b0['born'], n_life=b0['n_life'], permanent=b0['permanent'],
                   q_end=b0['q_end'], q_max=b0['q_max'], D2=b0['D2'], Dneg=b0['D_first_neg'], R3=b2['R'], born3=b2['born'], virt_born=(b1['born'] if b1 else None), virt_C1=(b1['C1'] if b1 else None),
                   ctrl_R=c0['R'], ctrl_born=c0['born'], ctrl_n_life=c0['n_life'], ctrl_permanent=c0['permanent'], ctrl_q_end=c0['q_end'], ctrl_gap=Cc['gap'], C_head=b0['C_head'][:12])
        rows.append(row)
        print(f"B Δ={Delta:.0f} r={r:4.2f}: gap={A['gap']:.5f} t_ρ={A['t_rho']:5.1f} n_max={A['n_max']} | {{1}}: R={b0['R']:.3f} рожд={b0['born']} жизнь={b0['n_life']} perm={b0['permanent']} q_end={b0['q_end']:.3f} D2={b0['D2']:+.1e} | {{2}} рожд={row['virt_born']} | ctrl R={c0['R']:.3f} perm={c0['permanent']} q_end={c0['q_end']:.3f} [{time.time()-t0:.0f}s]", flush=True)
    res['B'][str(int(Delta))] = dict(Delta=Delta, Omega_R=OmR, R_sc=Rsc, tau=tau, rows=rows)
V = res['verdict']; ctrl_Rmax = {'20': 7.587, '40': 9.039}; pilot_Rmax10 = 4.48
def rowsof(D): return res['B'][D]['rows']
V['PQ1'] = {D: dict(finite_le_09=all((not r['permanent']) for r in rowsof(D) if 0 < r['r'] <= 0.9), perm_ge_105=all(r['permanent'] for r in rowsof(D) if r['r'] >= 1.05)) for D in ('20', '40')}
V['PQ1']['ok'] = all(V['PQ1'][D]['finite_le_09'] and V['PQ1'][D]['perm_ge_105'] for D in ('20', '40'))
V['K1'] = any((r['permanent'] and r['r'] <= 0.8) or ((not r['permanent']) and r['r'] >= 1.2) for D in ('20', '40') for r in rowsof(D))
V['PQ2'] = {D: dict(Rmax=max((r['R'] or 0) for r in rowsof(D)), r_at=max(rowsof(D), key=lambda r: (r['R'] or 0))['r'], lo=0.77 * ctrl_Rmax[D], hi=ctrl_Rmax[D]) for D in ('20', '40')}
V['PQ2']['ok'] = all(V['PQ2'][D]['lo'] <= V['PQ2'][D]['Rmax'] <= V['PQ2'][D]['hi'] for D in ('20', '40')) and V['PQ2']['40']['Rmax'] > V['PQ2']['20']['Rmax'] > pilot_Rmax10
V['K2'] = bool(V['PQ2']['40']['Rmax'] <= V['PQ2']['20']['Rmax'] or V['PQ2']['20']['Rmax'] < pilot_Rmax10)
V['PQ3'] = {D: dict(D2neg_all=all(r['D2'] < 0 for r in rowsof(D) if r['born'] and 0.1 <= r['r'] <= 3)) for D in ('20', '40')}; V['PQ3']['ok'] = all(V['PQ3'][D]['D2neg_all'] for D in ('20', '40'))
V['K3'] = any(r['permanent'] and r['r'] <= 2 and r['D2'] > 0 for D in ('20', '40') for r in rowsof(D))
V['PQ4'] = dict(virt_births=int(sum(bool(r['virt_born']) for D in ('20', '40') for r in rowsof(D) if r['r'] > 0))); V['PQ4']['ok'] = V['PQ4']['virt_births'] == 0
def dev(D): return {str(r['r']): abs(r['ctrl_R'] - r['R']) / r['R'] for r in rowsof(D) if 0.5 <= r['r'] <= 3 and r['r'] != 1.0 and r['R']}
V['PQ5'] = {D: dict(dev=dev(D), maxdev=max(dev(D).values()), ctrl_switch=[(r['r'], r['ctrl_permanent']) for r in rowsof(D) if 0.85 <= r['r'] <= 1.1],
                    r_gapmax=max(rowsof(D), key=lambda r: r['gap'])['r']) for D in ('20', '40')}
V['PQ5']['ok'] = bool(V['PQ5']['20']['maxdev'] <= 0.18 and V['PQ5']['40']['maxdev'] <= 0.10
                      and all(all((not p) for rr, p in V['PQ5'][D]['ctrl_switch'] if rr <= 0.9) and all(p for rr, p in V['PQ5'][D]['ctrl_switch'] if rr >= 1.05) for D in ('20', '40'))
                      and all(0.9 <= V['PQ5'][D]['r_gapmax'] <= 1.0 for D in ('20', '40')))
V['K5'] = any(V['PQ5'][D]['maxdev'] > 0.30 for D in ('20', '40'))
def tail(D): return [r['R'] for r in rowsof(D) if r['r'] >= 1.05]
V['PQ6'] = {D: dict(R5=[r['R'] for r in rowsof(D) if r['r'] == 5][0], spearman=float(spearmanr([r['r'] for r in rowsof(D) if r['r'] >= 1.05], tail(D))[0])) for D in ('20', '40')}
V['PQ6']['ok'] = all(1.0 <= V['PQ6'][D]['R5'] <= 1.6 and V['PQ6'][D]['spearman'] == -1.0 for D in ('20', '40'))
V['K0'] = bool((not V['PQ8']['ok']) or V['PQ4']['virt_births'] > 0)
json.dump(res, open(OUT, 'w'), default=float); print('ВЕРДИКТ', json.dumps(V, ensure_ascii=False, default=float)); print('ГОТОВО', f'{time.time()-t0:.0f}s')
