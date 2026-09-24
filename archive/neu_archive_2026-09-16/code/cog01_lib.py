"""COG-01 — рождение уровня при огрублении: сжатие оператора переноса в L²(π), числовой радиус, огрубления-разбиения.
Геометрия: A = D^{1/2} P D^{-1/2}, D = diag(π); A₀ — сужение на ортодополнение к √π; ρ = spr(A₀), w = числовой радиус A₀."""
import numpy as np, itertools

def stationary(P):
    w, v = np.linalg.eig(P.T); i = np.argmin(np.abs(w - 1)); pi = np.real(v[:, i]); pi = pi / pi.sum()
    return np.maximum(pi, 1e-300)

def sym_form(P, pi):
    d = np.sqrt(pi); return (d[:, None] * P) / d[None, :]

def restrict(A, pi):
    """сужение A на ортодополнение к √π (ортонормированный базис дополнения)"""
    n = len(pi); u = np.sqrt(pi); u = u / np.linalg.norm(u)
    Q, _ = np.linalg.qr(np.column_stack([u, np.eye(n)[:, :n - 1]]))  # первый столбец ∝ u
    if np.dot(Q[:, 0], u) < 0: Q[:, 0] *= -1
    B = Q[:, 1:]; return B.T @ A @ B

def numerical_radius(M, n_angles=720):
    """w(M) = max_θ λ_max(Re(e^{-iθ} M)) — точная формула для числового радиуса"""
    best = 0.0
    for th in np.linspace(0, 2 * np.pi, n_angles, endpoint=False):
        H = (np.exp(-1j * th) * M + np.exp(1j * th) * M.conj().T) / 2; best = max(best, float(np.linalg.eigvalsh(H)[-1]))
    return best

def spectral_radius(M):
    ev = np.linalg.eigvals(M); return float(np.max(np.abs(ev))) if len(ev) else 0.0

def lump(P, pi, blocks):
    """сжатие P на подпространство Y-измеримых функций: P_Y[I,J] = Σ_{i∈I} π_i Σ_{j∈J} P_ij / π_I; blocks — массив меток"""
    labs = np.unique(blocks); K = len(labs); PY = np.zeros((K, K)); piY = np.zeros(K)
    for a, I in enumerate(labs):
        mI = blocks == I; piY[a] = pi[mI].sum()
        for b, J in enumerate(labs):
            mJ = blocks == J; PY[a, b] = (pi[mI][:, None] * P[np.ix_(mI, mJ)]).sum() / piY[a]
    return PY, piY

def lambda2(PY):
    ev = np.linalg.eigvals(PY); ev = ev[np.argsort(-np.abs(ev))]
    return float(np.abs(ev[1])) if len(ev) > 1 else 0.0

def analyze_chain(P, pi=None, partitions=None, rng=None, n_random=0, n_blocks=2, tol=1e-9):
    n = len(P); pi = stationary(P) if pi is None else pi; A0 = restrict(sym_form(P, pi), pi)
    rho = spectral_radius(A0); w = numerical_radius(A0); delta = w - rho
    if partitions is None:
        if rng is None: rng = np.random.default_rng(0)
        partitions = []
        for _ in range(n_random):
            b = rng.integers(0, n_blocks, n)
            if len(np.unique(b)) >= 2: partitions.append(b)
    births, l2s = [], []
    for b in partitions:
        PY, _ = lump(P, pi, np.asarray(b)); l2 = lambda2(PY); l2s.append(l2); births.append(l2 > rho + tol)
    l2s = np.array(l2s); over = bool(np.any(l2s > w + 1e-7)) if len(l2s) else False
    u = [(l - rho) / delta for l, bth in zip(l2s, births) if bth and delta > 1e-12]
    return dict(n=n, rho=rho, w=w, delta=delta, n_part=len(partitions), n_birth=int(np.sum(births)), frac_birth=(float(np.mean(births)) if len(births) else None),
                max_l2=(float(l2s.max()) if len(l2s) else None), bound_violated=over, u_median=(float(np.median(u)) if u else None), u_max=(float(np.max(u)) if u else None))

def all_bipartitions(n):
    out = []
    for r in range(1, n // 2 + 1):
        for S in itertools.combinations(range(n), r):
            if r == n / 2 and 0 not in S: continue
            b = np.ones(n, int); b[list(S)] = 0; out.append(b)
    return out

def random_reversible(n, rng):
    W = rng.exponential(size=(n, n)); W = (W + W.T) / 2; P = W / W.sum(1, keepdims=True); return P

def random_chain(n, rng):
    return rng.dirichlet(np.ones(n), size=n)
