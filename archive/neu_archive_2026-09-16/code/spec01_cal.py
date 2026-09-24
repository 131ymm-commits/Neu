"""SPEC-01 калибровка на ПОТРАЧЕННЫХ сидах (LJ13 41/42; дипептид cal400/cal500): сколько мод разрешается при малом лаге,
и как выглядят лог-зазоры. Не тест. Также — точный спектр синаевского ландшафта для проверки численной точности."""
import numpy as np, sys, time, glob
sys.path.insert(0, '/home/claude')
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
from scipy.linalg import eigh_tridiagonal
from lj13 import simulate

def its_ml(lab, tau, k_ts=14):
    c = TransitionCountEstimator(lagtime=tau, count_mode='effective').fit_fetch(lab.astype(int)).submodel_largest()
    m = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    return np.sort(m.timescales(k_ts))[::-1], c.n_states

def report(name, lab, taus):
    for tau in taus:
        ts, ns = its_ml(lab, tau); res = ts[ts > tau]
        s = np.log(res[:-1] / res[1:]) if len(res) > 1 else np.array([])
        print(f"  {name} τ={tau}: состояний {ns}, ITS>τ: {len(res)} из {len(ts)} | ITS {np.round(ts[:10],1)} | лог-зазоры {np.round(s[:8],2)}", flush=True)

t0 = time.time()
for T in (0.18, 0.28, 0.36):
    for s in (41, 42):
        r = simulate(T, s, 500000, rec_every=50); F = np.sort(r['D'][300:], axis=1)
        for k in (30, 100):
            lab = microstates(F, k, seed=0); report(f'LJ T={T} s{s} k={k}', lab, (2, 4, 8, 16))
        print(f'  [{time.time()-t0:.0f}s]')
for f in sorted(glob.glob('/home/claude/neu_archive/results/md_raw/mol_ala2_cal*.npz')):
    d = np.load(f); sc = d['scal']; phi, psi = sc[:, 0], sc[:, 1]; F = np.column_stack([np.cos(phi), np.sin(phi), np.cos(psi), np.sin(psi)])
    for k in (30, 100):
        lab = microstates(F, k, seed=0); report(f'DIP {f[-10:-4]} k={k}', lab, (2, 5, 10, 25))
# Синай: точность точной диагонализации
rng = np.random.default_rng(0); L = 4096; U = np.cumsum(rng.standard_normal(L)); U -= U.min()
theta = 0.075; T = theta * np.sqrt(L)
# скорости: w_{i->i+1} = 0.5*exp(-(U_{i+1}-U_i)/(2T)); симметризованный генератор: диагональ -(w_right+w_left), внедиагональ sqrt(w_ij w_ji)
wr = 0.5 * np.exp(-(U[1:] - U[:-1]) / (2 * T)); wl = 0.5 * np.exp(-(U[:-1] - U[1:]) / (2 * T))
diag = np.zeros(L); diag[:-1] -= wr; diag[1:] -= wl; off = np.sqrt(wr * wl)
t1 = time.time(); ev = eigh_tridiagonal(diag, off, select='i', select_range=(L - 14, L - 1), eigvals_only=True)
ev = np.sort(-ev)[::-1]  # -λ: 0 (стационар), затем малые положительные
print(f"Синай L={L} θ={theta}: время {time.time()-t1:.2f}s; -λ: {ev[:6]}; макс глубина/T = {(U.max()-U.min())/T:.1f}")
ts = 1.0 / ev[1:]; s = np.log(ts[:-1] / ts[1:]); print("  времена:", np.round(np.log10(ts[:8]), 2), "лог-зазоры:", np.round(s[:8], 2), "k*s_k:", np.round(np.arange(1, 9) * s[:8], 2))
