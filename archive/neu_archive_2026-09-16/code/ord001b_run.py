"""ORD-001b — hysteresis loop with calibrated window and hot-seeded down branch. Per PREREG."""
import json, sys, os, time
import numpy as np

exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])

M = 10
SEED = 20260846
GRAPHS = [5201, 5202, 5203, 5204, 5205]
KAPPAS = np.linspace(1.0, 60.0, 300)
RELAX = 20000
CKPT = "/home/claude/ord001b_ckpt.json"

def h2(n): return n * n / (16.0 + n * n)
def h1(n): return n / (4.0 + n)

def mf_relax(A, kap, hfun, n0, steps=RELAX):
    n = n0.copy()
    for _ in range(steps):
        n += 0.01 * (EPS + kap * (A.T @ hfun(n)) - n)
    return n

def sweep_loop(A, hfun):
    up = []
    n = np.full(M, EPS)
    for k in KAPPAS:
        n = mf_relax(A, k, hfun, n)
        up.append(n.sum())
    dn = []
    n = mf_relax(A, KAPPAS[-1], hfun, np.full(M, 12.0), 60000)   # hot seed at kappa_max
    for k in KAPPAS[::-1]:
        n = mf_relax(A, k, hfun, n)
        dn.append(n.sum())
    dn = dn[::-1]
    up, dn = np.array(up), np.array(dn)
    rng_mass = max(up.max(), dn.max()) - min(up.min(), dn.min())
    A_loop = float(np.sum(np.abs(up - dn)) * (KAPPAS[1] - KAPPAS[0]) /
                   (rng_mass * (KAPPAS[-1] - KAPPAS[0]) + 1e-12))
    # lower fold of loop: last kappa (from below) where branches differ by > 0.5 mass
    diff = np.abs(up - dn) > 0.5
    k_lo = float(KAPPAS[np.flatnonzero(diff)[0]]) if diff.any() else None
    return A_loop, k_lo

ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
t0 = time.time()
args = sys.argv[1:] if len(sys.argv) > 1 else [str(g) for g in GRAPHS]
for gs in args:
    sg = int(gs)
    if gs in ck: continue
    edges = edges_seq(M, sg)
    A = adj_at(edges, M, k_cycle(edges, M))
    e = {}
    for hname, hfun in (("h2", h2), ("h1", h1)):
        A_loop, k_lo = sweep_loop(A, hfun)
        e[hname] = dict(A_loop=A_loop, k_lo=k_lo)
        print(f"g{sg} {hname}: A_loop={A_loop:.3f} нижний фолд={k_lo} [{time.time()-t0:.0f}s]", flush=True)
    ck[gs] = e
    json.dump(ck, open(CKPT, "w"), default=float)

if all(str(g) in ck for g in GRAPHS):
    D1 = json.load(open("/home/claude/ord001_results.json"))
    h2A = [ck[str(g)]["h2"]["A_loop"] for g in GRAPHS]
    h1A = [ck[str(g)]["h1"]["A_loop"] for g in GRAPHS]
    pp1 = (sum(1 for a in h2A if a >= 0.2) >= 4 and all(a <= 0.05 for a in h1A))
    pp1_kill = (sum(1 for a in h2A if a <= 0.05) >= 2 or sum(1 for a in h1A if a >= 0.2) >= 2)
    dk = KAPPAS[1] - KAPPAS[0]
    agree = []
    for g in GRAPHS:
        klo = ck[str(g)]["h2"]["k_lo"]
        two_lo = D1[str(g)]["h"]["h2"]["split_lo"]
        if klo is not None and two_lo is not None:
            agree.append(abs(klo - two_lo) <= 2 * dk + 1e-9)
    pp2 = all(agree) and len(agree) == 5
    loo = all(sum(1 for j, g in enumerate(GRAPHS) if j != i and ck[str(g)]["h2"]["A_loop"] >= 0.2) >= 3
              and all(ck[str(g)]["h1"]["A_loop"] <= 0.05 for j, g in enumerate(GRAPHS) if j != i)
              for i in range(5))
    ck["verdicts"] = dict(h2A=h2A, h1A=h1A, PP1=bool(pp1), PP1_killed=bool(pp1_kill),
                          PP2=bool(pp2), loo_ok=bool(loo))
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"\nP-P1: {'ПОДТВЕРЖДЁН' if pp1 else ('УБИТ' if pp1_kill else 'не установлен')} "
          f"(h2: {[round(a,2) for a in h2A]}; h1: {[round(a,3) for a in h1A]}; LOO={loo})")
    print(f"P-P2 (фолд ↔ двухстартовое окно): {'подтверждён' if pp2 else 'не подтверждён'} ({sum(agree)}/5)")
print(f"[{time.time()-t0:.0f}s]")
