"""SORT-02 — пилот (калибровка): (i) телеграфы (5 сидов, k = 30, τ = 1, вложение 4) — оценённые цепи, описание PCCA(2): ρ, ρ₊, a₊, знак ведущей моды;
(ii) траектории лифтированного ходока с шумом (L = 64, c = 3.1, s = 0.02; 3 сида, 2·10⁵ шагов) — оценённая MSM на 2L состояниях,
описание «средний разрез»: a₊ оценённый против точного (1.9); (iii) точный lifted_local L = 32 по s — структура по ρ₊ (тест — 64, 128)."""
import numpy as np, json, time, warnings
warnings.filterwarnings('ignore')
from sort02_lib import spectrum_info, indicator, analyze_description
from sort01_lib import lifted_local
from cog01_lib import stationary
from hor02_lib import telegraph
from zeta01_lib import embed
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
t0 = time.time(); out = dict(tel=[], lift_est=[], lift_exact={})
def est_P(lab, tau):
    c = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch(lab.astype(int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=False).fit(c).fetch_model(); msr = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    return np.asarray(msm.transition_matrix), np.asarray(msm.stationary_distribution), np.asarray(msr.pcca(2).assignments), np.asarray(c.state_symbols)
# (i) телеграфы
for s in range(5):
    rng = np.random.default_rng(1000 * 40 + s); x, _ = telegraph(8000, 40, rng); lab = microstates(embed(x, 4), 30, seed=0); P, pi, pcca, _ = est_P(lab, 1)
    h = indicator(pi, pcca); r = analyze_description(P, pi, h)
    out['tel'].append(r); print(f"tel s={s}: ρ={r['rho']:.4f} ρ₊={r['rho_plus']:.4f} real₊={r['real_plus']} θ₊={r['theta_plus']:.3f} | C1={r['C1']:.4f} born_ρ={r['born_rho']} born₊={r['born_plus']} a₊={r['a_plus']:.3f} Σa={r['a_sum']:.3f} perm₊={r['permanent_plus']} late₊={r['late_plus']} [{time.time()-t0:.0f}s]", flush=True)
# (ii) оценённые лифтированные цепи
L, c, s = 64, 3.1, 0.02; Pex = lifted_local(L, c / L, s); piex = stationary(Pex); xs = np.repeat(np.arange(1, L + 1), 2); hmid = indicator(piex, (xs <= L // 2).astype(int)); rex = analyze_description(Pex, piex, hmid)
print(f"точная L={L} c={c} s={s}: ρ={rex['rho']:.5f} ρ₊={rex['rho_plus']:.5f} real₊={rex['real_plus']} a₊={rex['a_plus']:.3f} perm₊={rex['permanent_plus']} q_end₊={rex['q_end_plus']:.3f}", flush=True)
cum = np.cumsum(Pex, 1)
for seed in (11, 12, 13):
    rng = np.random.default_rng(seed); n_steps = 200000; traj = np.empty(n_steps, int); st = rng.integers(2 * L)
    u = rng.random(n_steps)
    for t in range(n_steps):
        traj[t] = st; st = int(np.searchsorted(cum[st], u[t]))
    cnt = TransitionCountEstimator(lagtime=1, count_mode='sliding').fit_fetch(traj).submodel_largest(); msm = MaximumLikelihoodMSM(reversible=False).fit(cnt).fetch_model()
    P = np.asarray(msm.transition_matrix); pi = np.asarray(msm.stationary_distribution); syms = np.asarray(cnt.state_symbols); h = indicator(pi, (xs[syms] <= L // 2).astype(int))
    r = analyze_description(P, pi, h); out['lift_est'].append(r)
    print(f"оценённая сид {seed} (состояний {len(P)}): ρ={r['rho']:.5f} ρ₊={r['rho_plus']:.5f} real₊={r['real_plus']} a₊={r['a_plus']:.3f} born₊={r['born_plus']} perm₊={r['permanent_plus']} q_end₊={r['q_end_plus']:.3f} [{time.time()-t0:.0f}s]", flush=True)
# (iii) точный lifted_local L = 32 по s
L = 32; xs = np.repeat(np.arange(1, L + 1), 2)
for s in (0.0, 0.02, 0.05, 0.1, 0.15, 0.2):
    rows = []
    for c in np.round(np.arange(1.5, 3.601, 0.05), 3):
        P = lifted_local(L, c / L, s); pi = stationary(P); h = indicator(pi, (xs <= L // 2).astype(int)); r = analyze_description(P, pi, h); r['c'] = float(c); rows.append(r)
    b_rho = [r['c'] for r in rows if r['born_rho']]; b_plus = [r['c'] for r in rows if r['born_plus']]; perm = [r['c'] for r in rows if r['permanent_plus']]
    cplx = [r['c'] for r in rows if not r['real_plus']]; late = [r['c'] for r in rows if r['late_plus']]
    out['lift_exact'][str(s)] = dict(win_rho=(min(b_rho), max(b_rho)) if b_rho else None, win_plus=(min(b_plus), max(b_plus)) if b_plus else None, perm_plus=perm, last_complex=(max(cplx) if cplx else None), late=(min(late), max(late)) if late else None)
    print(f"L=32 s={s}: окно по ρ {out['lift_exact'][str(s)]['win_rho']}, по ρ₊ {out['lift_exact'][str(s)]['win_plus']}; постоянные₊ {perm[:3]}…{perm[-2:] if perm else ''}; компл.₊ до {out['lift_exact'][str(s)]['last_complex']}; поздние₊ {out['lift_exact'][str(s)]['late']} [{time.time()-t0:.0f}s]", flush=True)
json.dump(out, open('/home/claude/sort02_pilot.json', 'w'), default=float); print('ГОТОВО', f'{time.time()-t0:.0f}s')
