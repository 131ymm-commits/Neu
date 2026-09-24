"""LEV-002 calibration v2: scan (eps, kap) for true bistability; pilots with hysteresis."""
import numpy as np, time
exec(open('/home/claude/lev002_calibrate.py').read().split('# mean-field')[0])  # graph defs, EDGES, K_cycle

def hill(n, ns): return n * n / (ns * ns + n * n)

def mf_attractors(A, eps, kap, ns, T=600.0, dt=0.01):
    def run(n0):
        n = n0.copy()
        for _ in range(int(T / dt)):
            n += dt * (eps + kap * (A.T @ hill(n, ns)) - n)
        return n
    dark = run(np.full(M, eps)).sum()
    hot = run(np.full(M, 12.0)).sum()
    return dark, hot

ns = 4.0
print("bistability scan (dark_sum vs hot_sum), K=4 and K=12, real graph + DAG K=12:")
for eps in (0.05, 0.10, 0.15):
    for kap in (9.0, 10.0, 12.0):
        d4, h4 = mf_attractors(adj_at(4), eps, kap, ns)
        d12, h12 = mf_attractors(adj_at(12), eps, kap, ns)
        dD, hD = mf_attractors(adj_at(12, dag=True), eps, kap, ns)
        print(f" eps={eps:.2f} kap={kap:4.1f}: K=4 {d4:5.2f}/{h4:5.2f}  K=12 {d12:5.2f}/{h12:5.2f}  "
              f"DAG12 {dD:5.2f}/{hD:5.2f}  bist4={int(h4-d4>4)} bist12={int(h12-d12>4)} dagMono={int(hD-dD<2)}")

def simulate_pilot(A, eps, kap, ns, ntraj, T, lo, hi, dt=0.005, ncap=60, seed=1, start='dark'):
    r = np.random.default_rng(seed)
    n = r.poisson(np.full((ntraj, M), eps)).astype(float) if start == 'dark' \
        else np.full((ntraj, M), 8.0)
    steps = int(T / dt)
    state = np.zeros(ntraj, dtype=int)  # 0 dark, 1 hot
    ups = np.zeros(ntraj); dns = np.zeros(ntraj)
    first_up = np.full(ntraj, np.nan)
    for s in range(steps):
        b = eps + kap * (hill(n, ns) @ A)
        n = np.clip(n + r.poisson(b * dt) - r.binomial(n.astype(int), 1 - np.exp(-dt)), 0, ncap)
        if s % 20 == 0:
            tot = n.sum(1)
            go_up = (state == 0) & (tot > hi)
            go_dn = (state == 1) & (tot < lo)
            t_now = s * dt
            first_up[np.isnan(first_up) & go_up] = t_now
            ups += go_up; dns += go_dn
            state = np.where(go_up, 1, np.where(go_dn, 0, state))
    return ups, dns, first_up

eps, kap = 0.10, 10.0
d12, h12 = mf_attractors(adj_at(12), eps, kap, ns)
lo, hi = d12 + 0.25 * (h12 - d12), d12 + 0.6 * (h12 - d12)
print(f"\npilots eps={eps} kap={kap}: hysteresis lo={lo:.1f} hi={hi:.1f}")
for K in (4, 6, 8, 10, 12):
    t0 = time.time()
    A = adj_at(K)
    ups, dns, fu = simulate_pilot(A, eps, kap, ns, 32, 800, lo, hi, seed=300 + K)
    n_ign = np.sum(~np.isnan(fu))
    Tig = np.nanmean(fu) if n_ign else np.inf
    tot_dn = dns.sum()
    print(f" K={K:2d}: ignited {n_ign}/32 by T=800 (mean T_ig~{Tig:6.1f}); "
          f"deignitions total={tot_dn:.0f}; ups total={ups.sum():.0f}  [{time.time()-t0:.0f}s]")
