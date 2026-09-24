"""LEV-002 calibration: quenched graph, mean-field, pilot switching times.
Allowed pre-prereg: graph analysis, deterministic ODE, coarse pilot switching
counts (N_tot threshold crossings). NO spectral detector on pilots.
"""
import numpy as np

M = 10
GRAPH_SEED = 4242
rng = np.random.default_rng(GRAPH_SEED)

# quenched ordered edge sequence: random ordered pairs i!=j, no repeats
pairs = [(i, j) for i in range(M) for j in range(M) if i != j]
rng.shuffle(pairs)
EDGES = pairs  # edge t: (j -> i) meaning j catalyzes production of i? define (src, dst)

def adj_at(K, dag=False):
    """A[j,i]=1 if j catalyzes i. dag=True: if edge closes a cycle, reverse it."""
    A = np.zeros((M, M), dtype=int)
    for t in range(K):
        s, d = EDGES[t]
        if dag:
            if creates_cycle(A, s, d):
                s, d = d, s
                if creates_cycle(A, s, d):
                    continue  # skip if both directions close (shouldn't happen from DAG)
        A[s, d] = 1
    return A

def creates_cycle(A, s, d):
    # adding s->d creates cycle iff path d ~> s exists
    seen = {d}; stack = [d]
    while stack:
        u = stack.pop()
        for v in np.where(A[u] == 1)[0]:
            if v == s: return True
            if v not in seen:
                seen.add(v); stack.append(v)
    return False

def has_cycle(A):
    # Kahn
    indeg = A.sum(0).copy()
    q = [i for i in range(M) if indeg[i] == 0]
    cnt = 0
    while q:
        u = q.pop()
        cnt += 1
        for v in np.where(A[u] == 1)[0]:
            indeg[v] -= 1
            if indeg[v] == 0: q.append(v)
    return cnt < M

K_cycle = None
for K in range(1, len(EDGES) + 1):
    if has_cycle(adj_at(K)):
        K_cycle = K; break
print(f"K_cycle (first directed cycle in quenched sequence) = {K_cycle}")
A_c = adj_at(K_cycle)
print("edges up to K_cycle:", EDGES[:K_cycle])

# mean-field
def hill(n, ns): return n * n / (ns * ns + n * n)

def mf_attractors(A, eps, kap, ns, T=400.0, dt=0.01):
    def run(n0):
        n = n0.copy()
        for _ in range(int(T / dt)):
            n += dt * (eps + kap * (A.T @ hill(n, ns)) - n)
        return n
    dark = run(np.full(M, eps))
    hot = run(np.full(M, kap))
    return dark.sum(), hot.sum()

eps, kap, ns = 0.6, 12.0, 4.0
print(f"\nmean-field with eps={eps} kap={kap} ns={ns} (d=1):")
K_born = None
for K in range(max(1, K_cycle - 4), K_cycle + 9):
    A = adj_at(K)
    dk, ht = mf_attractors(A, eps, kap, ns)
    born = (ht - dk) > 5.0
    if born and K_born is None: K_born = K
    Ad = adj_at(K, dag=True)
    dkD, htD = mf_attractors(Ad, eps, kap, ns)
    print(f" K={K:2d} cyc={int(has_cycle(A))} dark={dk:6.2f} hot={ht:6.2f} "
          f"| DAG: cyc={int(has_cycle(Ad))} dark={dkD:6.2f} hot={htD:6.2f}")
print(f"K_born (mean-field bistable, N_hot-N_dark>5) = {K_born}")

# pilot stochastic switching (tau-leap), coarse; NO detector here
def simulate(A, eps, kap, ns, ntraj, T, dt=0.005, ncap=60, seed=1, record_every=None, thresh=None):
    rngs = np.random.default_rng(seed)
    n = np.full((ntraj, M), eps)
    n = rngs.poisson(n).astype(float)
    steps = int(T / dt)
    up_cnt = np.zeros(ntraj); dn_cnt = np.zeros(ntraj)
    state_hi = np.zeros(ntraj, dtype=bool)
    tot_hist = []
    for s in range(steps):
        b = eps + kap * (hill(n, ns) @ A)          # (ntraj,M) x (M,M) -> catalysts j: n[:,j] -> A[j,i]
        births = rngs.poisson(b * dt)
        deaths = rngs.binomial(n.astype(int), 1 - np.exp(-dt))
        n = np.clip(n + births - deaths, 0, ncap)
        if thresh is not None and s % 20 == 0:
            tot = n.sum(1)
            hi = tot > thresh
            up_cnt += (~state_hi) & hi
            dn_cnt += state_hi & (~hi)
            state_hi = hi
        if record_every and s % record_every == 0:
            tot_hist.append(n.sum(1).copy())
    return n, up_cnt, dn_cnt, np.array(tot_hist)

import time
for eps_try in (0.4, 0.6, 0.8):
    dk, ht = mf_attractors(adj_at(K_cycle + 2), eps_try, kap, ns)
    thresh = 0.5 * (dk + ht)
    t0 = time.time()
    for K in (K_cycle, K_cycle + 2, K_cycle + 5):
        A = adj_at(K)
        _, up, dn, _ = simulate(A, eps_try, kap, ns, ntraj=24, T=600, seed=100 + K, thresh=thresh)
        # crude rates: transitions counted with 0.1-unit granularity (s%20, dt .005)
        print(f" eps={eps_try} K={K} (cyc={int(has_cycle(A))}): mean up={up.mean():.2f} "
              f"mean dn={dn.mean():.2f} per 600u  thresh={thresh:.1f}")
    print(f"   [{time.time()-t0:.0f}s]")
