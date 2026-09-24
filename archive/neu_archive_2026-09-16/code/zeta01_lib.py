"""Библиотека ZETA-01: вложение задержек + спектральный тест SPEC-01 (байесовский постериор MSM, реньевски-нормированные лог-зазоры)."""
import numpy as np, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import BayesianMSM, MaximumLikelihoodMSM

def embed(x, m=4, step=1):
    x = np.asarray(x, float); n = len(x) - (m - 1) * step
    return np.column_stack([x[i * step: i * step + n] for i in range(m)])

def spacing_stats(ts, tau):
    r = ts[ts > tau]
    if len(r) < 4: return None
    s = np.log(r[:-1] / r[1:]); k = np.arange(1, len(s) + 1); z = k * s
    return dict(p1=float(np.exp(-z[0] / z[1:].mean())), z1_rest=float(z[0] / z[1:].mean()), m=len(s), z=[float(v) for v in z[:6]])

def zeta(F, tau, k, ns=200, name='', seed=0, verbose=True):
    lab = microstates(F, k, seed=seed)
    c = TransitionCountEstimator(lagtime=tau, count_mode='effective').fit_fetch(lab.astype(int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model(); post = BayesianMSM(n_samples=ns, reversible=True).fit(msm).fetch_model()
    ml = spacing_stats(np.sort(msm.timescales(14))[::-1], tau); ps, zr, ms = [], [], []
    for mm in post.samples:
        st = spacing_stats(np.sort(mm.timescales(14))[::-1], tau)
        if st is None: ms.append(0); continue
        ps.append(st['p1']); zr.append(st['z1_rest']); ms.append(st['m'])
    unresolved = np.mean(np.array(ms) < 3) > 0.5; PL = float(np.mean(np.array(ps) <= 0.05)) if ps else 0.0
    dec = 'отказ:не разрешён' if unresolved else ('уровень' if PL >= 0.95 else ('нет' if PL <= 0.05 else 'отказ'))
    r = dict(n=int(len(F)), k=k, tau=tau, n_states=int(c.n_states), its_ml=[float(x) for x in np.sort(msm.timescales(14))[::-1][:6]], z_ml=(ml['z'] if ml else None),
             p1_ml=(ml['p1'] if ml else None), PL=PL, zeta_median=(float(np.median(zr)) if zr else None), zeta_q=([float(x) for x in np.quantile(zr, [0.05, 0.95])] if zr else None), m_median=float(np.median(ms)), dec=dec)
    if verbose: print(f"{name:32s} n={r['n']:6d} k={k} τ={tau} | ITS {np.round(r['its_ml'][:5], 1)} | z {None if not r['z_ml'] else np.round(r['z_ml'][:4], 2)} | ζ {None if r['zeta_median'] is None else round(r['zeta_median'], 2)} [{None if not r['zeta_q'] else np.round(r['zeta_q'], 2)}] P_L {PL:.2f} → {dec}", flush=True)
    return r
