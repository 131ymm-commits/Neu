"""VIRT-01 — пилоты для калибровки кромок. (A) V = 0.8 (a = 5, a² = 25) и свободная цепочка; N = 6000, τ = 1.
(B) Δ = 10 (γ = 2, Ω = 1 ⇒ Ω_R = 0.05, R_sc = 0.005, EP при γ_g = 0.1), свип γ_g, лаг τ = 0.2/Ω_R = 4; контроль — двухуровневая
система с теми же Ω_R, Γ₁, Γ₂. Тестовые Δ (прогон) — 20 и 40."""
import numpy as np, json, time
from virt01_lib import *
t0 = time.time(); out = dict(A={}, B={})
# ---- (A)
N, nmax = 6000, 2000
for V in (0.0, 0.8, 1.2):
    w, a0, C = chain_corr(N, V, nmax); nc, eps = crossover(C); D = memory(C); E = implied_energy(C)
    a = None if V == 1 else -1 / (1 - V)
    out['A'][V] = dict(nc=nc, a2=(a * a if a else None), ratio=(nc / (a * a) if (nc and a) else None), eps_at=[float(eps[k]) for k in (1, 3, 9, 30, 99, 299, 999, 1999)],
                       Dmin=float(D[1:].min()), E_last=float(E[-1]), E_b=(-(V + 1 / V) + 2 if V > 1 else None), Omega=float(C[1] / C[0]), rho=float(np.exp(-w[0])))
    print(f"A: V={V}: n_c={nc}, a²={out['A'][V]['a2']}, n_c/a²={out['A'][V]['ratio']}; ε(n) при n=2,4,10,31,100,300,1000,2000: {np.round(out['A'][V]['eps_at'],3)}; min D={out['A'][V]['Dmin']:.2e}; E(2000)={out['A'][V]['E_last']:.5f}, E_b={out['A'][V]['E_b']}; Ω={out['A'][V]['Omega']:.5f} ρ={out['A'][V]['rho']:.6f} [{time.time()-t0:.0f}s]", flush=True)
# ---- (B)
gamma, Omega, Delta = 2.0, 1.0, 10.0; OmR = Omega ** 2 / (2 * Delta); Rsc = gamma * Omega ** 2 / (4 * Delta ** 2); tau = 0.2 / OmR
print(f"B: Ω_R={OmR}, R_sc={Rsc}, EP γ_g*={2*OmR}, τ={tau}")
for gg in (0.0, 0.01, 0.02, 0.05, 0.08, 0.09, 0.1, 0.11, 0.12, 0.15, 0.2, 0.3, 0.5, 1.0):
    Ls = lambda_system(Omega, Delta, gamma, gg); res = description_analysis(Ls, 3, tau, [[0], [2], [1]])
    Lc = two_level_control(OmR, Rsc, Rsc + gg); resc = description_analysis(Lc, 2, tau, [[0]])
    b0 = res['blocks']['[0]']; b1 = res['blocks']['[1]']; c0 = resc['blocks']['[0]']
    out['B'][gg] = dict(rho=res['rho'], gap=res['gap'], t_rho=res['t_rho'], n_max=res['n_max'], pi=res['pi'], R=b0['R'], born=b0['born'], n_life=b0['n_life'], permanent=b0['permanent'], q_end=b0['q_end'], q_max=b0['q_max'], D2=b0['D2'], Dneg=b0['D_first_neg'],
                        virt_born=b1['born'], virt_C1=b1['C1'], ctrl_R=c0['R'], ctrl_born=c0['born'], ctrl_n_life=c0['n_life'], ctrl_permanent=c0['permanent'], ctrl_q_end=c0['q_end'], ctrl_gap=resc['gap'])
    print(f"  γ_g={gg:5.2f} r={gg/(2*OmR):4.2f}: gap={res['gap']:.5f} t_ρ={res['t_rho']:5.1f} n_max={res['n_max']} | {{1}}: C1={b0['C1']:.5f} R={b0['R']:.3f} рожд={b0['born']} жизнь={b0['n_life']} perm={b0['permanent']} q_end={b0['q_end']:.3f} q_max={b0['q_max']:.3f} D2={b0['D2']:+.2e} D<0 с n={b0['D_first_neg']} | {{2}}: рожд={b1['born']} C1={b1['C1']:.1e} | контроль: R={c0['R']:.3f} жизнь={c0['n_life']} perm={c0['permanent']} q_end={c0['q_end']:.3f} [{time.time()-t0:.0f}s]", flush=True)
json.dump(out, open('/home/claude/virt01_pilot.json', 'w'), default=float); print('ГОТОВО', f'{time.time()-t0:.0f}s')
