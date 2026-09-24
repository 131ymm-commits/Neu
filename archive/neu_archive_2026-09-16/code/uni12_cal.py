"""UNI-12 pre-freeze calibration on SPENT seeds (940003 k=3, 940012 k=12) — arithmetic for prereg edges.
Psi formula per ReconcilingEmergences/EmergencePsi.m (Gaussian MI, tau=1)."""
import numpy as np

exec(open("/home/claude/del001_run.py").read().split("t0 = time.time()")[0])

def sim_multi(k, seed, ntraj=5):
    """Structural copy of del001 sim recording ALL k nodes."""
    rng = np.random.default_rng(seed)
    n = np.full((ntraj, k), int(round(1.0514 * OMEGA)), dtype=np.int64)
    steps = int(T_TOT / DT); burn = int(T_BURN / DT); stride = int(REC_DT / DT)
    rec = np.empty((ntraj, NS, k))
    ustar = 1.0514 ** H
    for i in range(steps):
        b1 = OMEGA * BETA / (1.0 + (n[:, -1] / OMEGA) ** H)
        births = np.empty((ntraj, k))
        births[:, 0] = b1
        births[:, 1:] = n[:, :-1]
        n = np.maximum(n + rng.poisson(births * DT) - rng.poisson(n * DT), 0)
        j = i - burn
        if j >= 0 and (j + 1) % stride == 0:
            idx = (j + 1) // stride - 1
            if idx < NS: rec[:, idx, :] = n / OMEGA
    return rec

def gmi(a, b):
    r = np.corrcoef(a, b)[0, 1]
    r = np.clip(r, -0.999999, 0.999999)
    return -0.5 * np.log(1 - r * r)

def psi(X, M, tau=1):
    """X: (T,k) micro; M: (T,) macro. Returns psi, psi_lenient, v_mi, sum_x_mi, max_x_mi."""
    v = gmi(M[:-tau], M[tau:])
    xs = [gmi(X[:-tau, j], M[tau:]) for j in range(X.shape[1])]
    return v - sum(xs), v - max(xs), v, sum(xs), max(xs)

RNGS = np.random.default_rng(777)
for k, seed in ((3, 940003), (12, 940012)):
    rec = sim_multi(k, seed, 3)
    for r in range(3):
        X = rec[r][-8000:]                       # (8000,k) stationary tail
        M = X.mean(1)
        p, pl, v, sx, mx = psi(X, M)
        Xs = X.copy(); RNGS.shuffle(Xs, axis=0)  # time-shuffle surrogate (joint rows shuffled)
        Ms = Xs.mean(1)
        ps, pls, *_ = psi(Xs, Ms)
        print(f"k={k} r={r}: psi={p:+.3f} psi'={pl:+.3f} (v_mi={v:.3f} sum_x={sx:.3f} max_x={mx:.3f}) | "
              f"суррогат: psi={ps:+.3f} psi'={pls:+.3f}", flush=True)
