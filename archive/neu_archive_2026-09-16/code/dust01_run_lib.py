"""Библиотека DUST: загрузка, признаки, тест (MSM + точная форма), отложенная половина, суррогаты."""
import numpy as np, sys, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import BayesianMSM, MaximumLikelihoodMSM
K = 15; TAU = 1; NS = 200; KTS = 14

def load(fn):
    rows = [l.split() for l in open(fn) if l.strip()]; a = np.array([float(r[0]) for r in rows]); d = np.array([float(r[1]) for r in rows]); ca = np.array([float(r[2]) for r in rows])
    o = np.argsort(a); a, d, ca = a[o], d[o], ca[o]; nan = np.isnan(ca); ca[nan] = np.interp(a[nan], a[~nan], ca[~nan]); return a, d, np.log(ca)
def std(x): return (x - x.mean(0)) / x.std(0)
def embed(x, m): n = len(x) - m + 1; return np.column_stack([x[i: i + n] for i in range(m)])
def p_rank1(z): m = len(z); g = z[0] / z.sum(); return float((1 - g) ** (m - 1))
def stats(ts, tau):
    r = ts[ts > tau]
    if len(r) < 4: return None
    s = np.log(r[:-1] / r[1:]); k = np.arange(1, len(s) + 1); z = np.maximum(k * s, 1e-12); return dict(m=len(z), zeta=float(z[0] / z[1:].mean()), p=p_rank1(z))
def test(F, k=K, tau=TAU, seed=0, ns=NS):
    lab = microstates(F, k, seed=seed).astype(int)
    c = TransitionCountEstimator(lagtime=tau, count_mode='effective').fit_fetch(lab).submodel_largest(); msm = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    post = BayesianMSM(n_samples=ns, reversible=True).fit(msm).fetch_model()
    S = [stats(np.sort(mm.timescales(KTS))[::-1], tau) for mm in post.samples]; ms = [s['m'] if s else 0 for s in S]; S = [s for s in S if s]
    unresolved = np.mean(np.array(ms) < 3) > 0.5; PL = float(np.mean([s['p'] <= 0.05 for s in S])) if S else 0.0
    dec = 'отказ:не разрешён' if unresolved else ('уровень' if PL >= 0.95 else ('нет' if PL <= 0.05 else 'отказ'))
    its = np.sort(msm.timescales(KTS))[::-1]
    return dict(n=int(len(F)), n_states=int(c.n_states), its=[float(x) for x in its[:6]], t1=float(its[0]), zeta=(float(np.median([s['zeta'] for s in S])) if S else None),
                zeta_q=([float(x) for x in np.quantile([s['zeta'] for s in S], [0.05, 0.95])] if S else None), PL=PL, dec=dec, m_median=float(np.median(ms)), lab=lab, msm=msm, c=c)
def heldout(F, k=K, tau=TAU, block=40):
    """обучение на нечётных блоках, тест на чётных: t1 обучения против t1 теста по автокорреляции собственного вектора"""
    lab = microstates(F, k, seed=0).astype(int); n = len(lab); bid = np.arange(n) // block; tr = bid % 2 == 0; te = ~tr
    # обучающая последовательность — конкатенация блоков (переходы на стыках блоков считаются; их ~n/(2·block))
    c = TransitionCountEstimator(lagtime=tau, count_mode='effective').fit_fetch(lab[tr]).submodel_largest(); msm = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    ts = np.sort(msm.timescales(KTS))[::-1]; ev = msm.eigenvectors_right(3)[:, 1]; sym = c.state_symbols
    f = np.array([ev[np.searchsorted(sym, s)] if s in set(sym) else np.nan for s in lab[te]]); ok = ~np.isnan(f)
    g = f[ok]; a = np.corrcoef(g[:-tau], g[tau:])[0, 1] if g.std() > 0 else 0.0; t_te = (-tau / np.log(a)) if a > 0 else 0.0
    return dict(t1_train=float(ts[0]), t1_test=float(t_te), ratio=(float(t_te / ts[0]) if ts[0] > 0 else None), n_train=int(tr.sum()), n_test=int(te.sum()))
def surrogate(x, rng):
    X = np.fft.rfft(x); ph = np.exp(1j * rng.uniform(0, 2 * np.pi, len(X))); ph[0] = 1; return np.fft.irfft(np.abs(X) * ph, n=len(x))

