"""LEV-002 shared code — everything per PREREG (frozen)."""
import numpy as np

M = 10
GRAPH_SEED = 4242
EPS, KAP, NS, NCAP = 0.10, 10.0, 4.0, 60
DT = 0.01
T_TRAJ = 400.0
STEPS = int(T_TRAJ / DT)          # 40000
REC_EVERY = 6                     # Drec = 0.06
NSAMP = STEPS // REC_EVERY        # 6666
BURN = int(0.05 * NSAMP)
DREC = REC_EVERY * DT
NTRAJ = 320
BUDGETS = {"B1": 20, "B2": 80, "B3": 320}
LAGS = [32, 64, 128, 256, 512]
LAG_MAIN = 256
PLATEAU = [128, 256, 512]
NBMAX = 81                        # N_tot clipped to 80, bin width 1
MINVIS = 50
SIM_SEED = 20260824

_r = np.random.default_rng(GRAPH_SEED)
pairs = [(i, j) for i in range(M) for j in range(M) if i != j]
_r.shuffle(pairs)
EDGES = pairs

def _creates_cycle(A, s, d):
    seen = {d}; stack = [d]
    while stack:
        u = stack.pop()
        for v in np.where(A[u] == 1)[0]:
            if v == s: return True
            if v not in seen: seen.add(v); stack.append(v)
    return False

def adj_at(K, dag=False):
    A = np.zeros((M, M), dtype=int)
    for t in range(K):
        s, d = EDGES[t]
        if dag and _creates_cycle(A, s, d):
            s, d = d, s
            if _creates_cycle(A, s, d): continue
        A[s, d] = 1
    return A

def hill(n): return n * n / (NS * NS + n * n)

def simulate(K, dag, ntraj, T, seed_tag):
    A = adj_at(K, dag=dag).astype(float)
    rng = np.random.default_rng(SIM_SEED + seed_tag)
    n = rng.poisson(np.full((ntraj, M), EPS)).astype(float)
    steps = int(T / DT)
    nsamp = steps // REC_EVERY
    rec = np.empty((ntraj, nsamp), dtype=np.int16)
    pdeath = 1 - np.exp(-DT)
    capfrac = 0
    for s in range(steps):
        b = EPS + KAP * (hill(n) @ A)
        n = n + rng.poisson(b * DT) - rng.binomial(n.astype(np.int64), pdeath)
        np.clip(n, 0, NCAP, out=n)
        if (s + 1) % REC_EVERY == 0:
            tot = n.sum(1)
            rec[:, (s + 1) // REC_EVERY - 1] = np.clip(tot, 0, 200)
        if s % 4000 == 0:
            capfrac += (n >= NCAP).mean()
    return rec[:, int(0.05 * nsamp):], capfrac / (steps / 4000)

def spectral(data, per_traj_main=False):
    b = np.clip(data.astype(np.int32), 0, NBMAX - 1)
    res = {}
    Cper = None
    for lag in LAGS:
        a0 = b[:, :-lag].ravel(); a1 = b[:, lag:].ravel()
        C = np.bincount(a0 * NBMAX + a1, minlength=NBMAX * NBMAX).reshape(NBMAX, NBMAX).astype(np.float64)
        C = C + C.T
        keep = C.sum(1) >= MINVIS
        if keep.sum() < 3:
            res[lag] = (np.nan, np.nan); continue
        Ck = C[np.ix_(keep, keep)]
        s = Ck.sum(1)
        A2 = Ck / np.sqrt(np.outer(s, s))
        evv = np.sort(np.linalg.eigvalsh((A2 + A2.T) / 2))[::-1]
        tau = lag * DREC
        lam2 = evv[1] if len(evv) > 1 else np.nan
        lam3 = evv[2] if len(evv) > 2 else np.nan
        t2 = -tau / np.log(lam2) if 0 < lam2 < 1 else np.nan
        t3 = -tau / np.log(lam3) if 0 < lam3 < 1 else np.nan
        res[lag] = (t2, t3)
        if lag == LAG_MAIN and per_traj_main:
            Cper = np.zeros((data.shape[0], NBMAX, NBMAX), dtype=np.int32)
            for j in range(data.shape[0]):
                Cper[j] = np.bincount(b[j, :-lag] * NBMAX + b[j, lag:],
                                      minlength=NBMAX * NBMAX).reshape(NBMAX, NBMAX)
    return res, Cper

def R_from_counts(C, tau=LAG_MAIN * DREC):
    C = C + C.T
    keep = C.sum(1) >= MINVIS
    if keep.sum() < 3: return np.nan
    Ck = C[np.ix_(keep, keep)].astype(np.float64)
    s = Ck.sum(1)
    A2 = Ck / np.sqrt(np.outer(s, s))
    evv = np.sort(np.linalg.eigvalsh((A2 + A2.T) / 2))[::-1]
    if len(evv) < 3 or not (0 < evv[1] < 1) or not (0 < evv[2] < 1): return np.nan
    return (-tau / np.log(evv[1])) / (-tau / np.log(evv[2]))

def analyze_budgets(rec):
    out = {}
    for bn, nt in BUDGETS.items():
        sub = rec[:nt]
        res, Cper = spectral(sub, per_traj_main=True)
        t2m, t3m = res[LAG_MAIN]
        Rm = t2m / t3m if (t2m == t2m and t3m == t3m) else np.nan
        t2s = [res[l][0] for l in PLATEAU]
        plateau = (not np.any(np.isnan(t2s))) and \
                  (np.max(t2s) - np.min(t2s)) / np.mean(t2s) < 0.20
        jr = []
        if Cper is not None:
            Ct = Cper.sum(0)
            for j in range(nt):
                jr.append(R_from_counts(Ct - Cper[j]))
        jr = np.array(jr, dtype=float)
        j16 = float(np.nanpercentile(jr, 16)) if len(jr) else np.nan
        j84 = float(np.nanpercentile(jr, 84)) if len(jr) else np.nan
        out[bn] = dict(R=None if Rm != Rm else float(Rm),
                       t2=None if t2m != t2m else float(t2m),
                       t3=None if t3m != t3m else float(t3m),
                       plateau=bool(plateau), j16=j16, j84=j84)
    return out
