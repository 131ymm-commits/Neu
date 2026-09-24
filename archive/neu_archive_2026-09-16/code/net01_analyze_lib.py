"""Библиотека анализа NET: analyze(lab, ind, tag) — MSM, ранг моды, ζ, решение."""
import numpy as np, time, sys, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import BayesianMSM, MaximumLikelihoodMSM
TAU = 2; KTS = 14; NS = 200; t0 = time.time()

def p_rank1(z): m = len(z); g = z[0] / z.sum(); return float((1 - g) ** (m - 1))
def stats(ts, tau):
    r = ts[ts > tau]
    if len(r) < 4: return None
    s = np.log(r[:-1] / r[1:]); k = np.arange(1, len(s) + 1); z = np.maximum(k * s, 1e-12); return dict(m=len(z), zeta=float(z[0] / z[1:].mean()), p=p_rank1(z))
def analyze(lab, ind, tag):
    """lab — метки состояний по кадрам; ind — индикатор икосаэдра по кадрам. Возвращает ранг моды, ζ, решение, занятости состояний над модой."""
    lab = lab.astype(int)
    c = TransitionCountEstimator(lagtime=TAU, count_mode='effective').fit_fetch(lab).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    # кадры в наибольшем связном множестве
    keep = np.isin(lab, c.state_symbols); sub = lab[keep]; ind_k = ind[keep]
    # собственные векторы (правые) как функции состояний → по кадрам
    ts = msm.timescales(KTS); order = np.argsort(ts)[::-1]; ts = ts[order]
    evecs = msm.eigenvectors_right(KTS + 1)[:, 1:][:, order]     # без стационарного
    idx = np.searchsorted(c.state_symbols, sub)
    cors = []
    for j in range(evecs.shape[1]):
        f = evecs[idx, j]; cors.append(abs(np.corrcoef(f, ind_k)[0, 1]) if f.std() > 0 and ind_k.std() > 0 else 0.0)
    cors = np.array(cors); r_ico = int(np.argmax(cors)) + 1; cmax = float(cors.max())
    if ind_k.std() == 0 or cmax < 0.3: r_ico = None
    # занятость состояний, «несущих» моды выше моды икосаэдра: состояния с максимальным |компонентом| в этих векторах
    pi = msm.stationary_distribution; above = []
    if r_ico and r_ico > 1:
        for j in range(r_ico - 1):
            s_max = int(np.argmax(np.abs(evecs[:, j]))); above.append(float(pi[s_max]))
    post = BayesianMSM(n_samples=NS, reversible=True).fit(msm).fetch_model()
    S = [stats(np.sort(mm.timescales(KTS))[::-1], TAU) for mm in post.samples]; ms = [s['m'] if s else 0 for s in S]; S = [s for s in S if s]
    unresolved = np.mean(np.array(ms) < 3) > 0.5; PL = float(np.mean([s['p'] <= 0.05 for s in S])) if S else 0.0
    dec = 'отказ:не разрешён' if unresolved else ('уровень' if PL >= 0.95 else ('нет' if PL <= 0.05 else 'отказ'))
    r = dict(n_states=int(c.n_states), frac_kept=float(keep.mean()), its=[float(x) for x in ts[:8]], r_ico=r_ico, corr_max=cmax, corr_top3=[float(x) for x in cors[:3]],
             occ_above=above, zeta=(float(np.median([s['zeta'] for s in S])) if S else None), PL=PL, dec=dec, m_median=float(np.median(ms)))
    print(f"  {tag:14s} сост {r['n_states']:4d} (кадров {r['frac_kept']:.3f}) ITS {np.round(r['its'][:5], 1)} | r_ico {r_ico} (|corr| {cmax:.2f}; топ-3 {np.round(cors[:3], 2)}) занятость над модой {np.round(above, 4)} | ζ {r['zeta']} P_L {PL:.2f} → {dec} [{time.time()-t0:.0f}s]", flush=True)
    return r

