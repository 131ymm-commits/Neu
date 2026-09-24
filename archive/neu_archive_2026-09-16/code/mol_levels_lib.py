"""Level-finding pipeline (frozen for MOL-001/002): microstates by k-means -> transition matrix at lag tau -> implied timescales gap ->
spectral assignment of macrostates (sign structure of slow eigenvectors / k-means on eigenvectors) -> psi' (discrete) vs random partitions -> dwell CV."""
import numpy as np
from scipy.cluster.vq import kmeans2

def microstates(F, k, seed=0):
    rng = np.random.default_rng(seed)
    Fz = (F - F.mean(0)) / (F.std(0) + 1e-12)
    cent, lab = kmeans2(Fz, k, minit="++", seed=seed, iter=30)
    return lab

def transition_matrix(lab, k, tau):
    C = np.zeros((k, k))
    np.add.at(C, (lab[:-tau], lab[tau:]), 1.0)
    C = C + C.T   # reversible symmetrization
    keep = C.sum(1) > 0
    P = C[keep][:, keep] / C[keep][:, keep].sum(1, keepdims=True)
    return P, keep

def implied_timescales(P, tau, n=6):
    w, V = np.linalg.eig(P); order = np.argsort(-np.real(w)); w = np.real(w[order]); V = np.real(V[:, order])
    w = np.clip(w[1:n + 1], 1e-9, 0.999999)
    return -tau / np.log(w), V[:, :n + 1]

def find_levels(lab, k, tau, gap_min=3.0, nmax=6):
    P, keep = transition_matrix(lab, k, tau)
    its, V = implied_timescales(P, tau, nmax)
    ratios = its[:-1] / its[1:]
    # number of slow processes m = largest m such that its[m-1]/its[m] >= gap_min (first gap from the top)
    m = 0
    for i, r in enumerate(ratios):
        if r >= gap_min: m = i + 1; break
    n_levels = m + 1 if m > 0 else 1
    # assign macrostates: k-means on the m slow eigenvectors (PCCA-like)
    micro_ids = np.flatnonzero(keep)
    if n_levels > 1:
        emb = V[:, 1:m + 1]
        _, mac = kmeans2(emb, n_levels, minit="++", seed=1, iter=50)
    else:
        mac = np.zeros(len(micro_ids), int)
    macro_of_micro = np.full(k, -1); macro_of_micro[micro_ids] = mac
    S = macro_of_micro[lab]
    return dict(its=its, ratios=ratios, n_levels=n_levels, S=S, macro_of_micro=macro_of_micro)

def disc_mi(a, b):
    ja = np.unique(a, return_inverse=True)[1]; jb = np.unique(b, return_inverse=True)[1]
    C = np.zeros((ja.max() + 1, jb.max() + 1)); np.add.at(C, (ja, jb), 1.0); p = C / C.sum()
    pa = p.sum(1, keepdims=True); pb = p.sum(0, keepdims=True); nz = p > 0
    return float((p[nz] * np.log(p[nz] / (pa @ pb)[nz])).sum())

def psi_prime(S, X, tau, nbins=8):
    """psi' = I(S_t;S_{t+tau}) - max_j I(x_j,t ; S_{t+tau}); micro x_j binned into nbins quantiles."""
    v = disc_mi(S[:-tau], S[tau:])
    best = -np.inf
    for j in range(X.shape[1]):
        q = np.quantile(X[:, j], np.linspace(0, 1, nbins + 1)[1:-1]); xb = np.searchsorted(q, X[:, j])
        best = max(best, disc_mi(xb[:-tau], S[tau:]))
    return v - best, v, best

def dwell_times(S, min_len=1):
    d = np.diff(S); ch = np.flatnonzero(d != 0) + 1
    seg = np.diff(np.concatenate([[0], ch, [len(S)]]))
    states = S[np.concatenate([[0], ch])]
    return seg, states

def committed(S, persist):
    """Transition-based assignment: a switch to a new state counts only if it persists >= `persist` frames; returns committed state series."""
    S = np.asarray(S); out = S.copy(); cur = S[0]; i = 0; n = len(S)
    while i < n:
        if S[i] != cur:
            j = i
            while j < n and S[j] == S[i]: j += 1
            if j - i >= persist: cur = S[i]; out[i:j] = cur; i = j; continue
            out[i:j] = cur; i = j
        else:
            out[i] = cur; i += 1
    return out

def microstates_fit(F, k, seed=0):
    mu = F.mean(0); sd = F.std(0) + 1e-12
    Fz = (F - mu) / sd
    cent, lab = kmeans2(Fz, k, minit="++", seed=seed, iter=30)
    return dict(cent=cent, mu=mu, sd=sd), lab

def assign(F, model):
    Fz = (F - model["mu"]) / model["sd"]
    d = ((Fz[:, None, :] - model["cent"][None, :, :]) ** 2).sum(-1)
    return d.argmin(1)
