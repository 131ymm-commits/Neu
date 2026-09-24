"""DET-016 — certificate of continuous (transcritical) birth. Per PREREG (frozen 2026-08-24)."""
import json, os, sys, time
import numpy as np

exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])

M = 10
SEED = 20260847
CYC = [5201, 5202, 5203, 5204, 5205]
DEG = [5206, 5207, 5208]
NK = 15
N_HOT = 40
T_ST = 100.0
STEPS = int(T_ST / DT)
BURN = int(0.3 * (STEPS // 100))
CKPT = "/home/claude/det016_ckpt.json"

def h1(n): return n / (4.0 + n)
def h2(n): return n * n / (16.0 + n * n)
def h1p(n): return 4.0 / (4.0 + n) ** 2
def h2p(n): return 32.0 * n / (16.0 + n * n) ** 2

def mf_relax(A, kap, hfun, n0, steps=30000):
    n = n0.copy()
    for _ in range(steps):
        n += 0.01 * (EPS + kap * (A.T @ hfun(n)) - n)
    return n

def abscissa(A, kap, hfun, hp):
    nd = mf_relax(A, kap, hfun, np.full(M, EPS))
    J = kap * (A.T * hp(nd)[None, :]).astype(float) - np.eye(M)
    # J_ij = d/dn_j [kap*(A^T h(n))_i] - delta = kap*A_ji*h'(n_j) - delta
    Jm = kap * (A.T * hp(nd)[None, :]) - np.eye(M)
    return float(np.max(np.linalg.eigvals(Jm).real)), nd

def kappa_c(A, hfun, hp):
    ks = np.linspace(1.0, 40.0, 120)
    best, bk = 1e9, None
    for k in ks:
        a, _ = abscissa(A, k, hfun, hp)
        if abs(a) < best: best, bk = abs(a), k
    return float(bk)

def rewire_acyclic(A, seed, attempts=200):
    rng = np.random.default_rng(seed)
    B = A.copy()
    for _ in range(attempts):
        es = np.argwhere(B == 1)
        if len(es) < 2: break
        i1, i2 = rng.choice(len(es), 2, replace=False)
        (a, b), (c, d) = es[i1], es[i2]
        if a == d or c == b or B[a, d] or B[c, b]: continue
        B2 = B.copy(); B2[a, b] = 0; B2[c, d] = 0; B2[a, d] = 1; B2[c, b] = 1
        if not has_cycle(B2, M): B = B2
    return B

def stat_MF_(A, kap, hfun, seed):
    """Stationary sim -> (median of traj means, median of per-traj Fano)."""
    rng = np.random.default_rng(seed)
    nd = mf_relax(A, kap, hfun, np.full(M, EPS))
    n = rng.poisson(np.maximum(nd, 0), size=(N_HOT, M)).astype(float)
    pdeath = 1 - np.exp(-DT)
    Af = A.astype(float)
    tot = []
    for s in range(STEPS):
        b = EPS + kap * (hfun(n) @ Af)
        n = np.clip(n + rng.poisson(b * DT) - rng.binomial(n.astype(np.int64), pdeath), 0, NCAP)
        if (s + 1) % 100 == 0:
            tot.append(n.sum(1).copy())
    X = np.array(tot)[BURN:]          # (nsamp, N_HOT)
    means = X.mean(0)
    varis = X.var(0)
    fano = varis / np.maximum(means, 1e-9)
    return float(np.median(means)), float(np.median(fano))

def curves(A, ks, hfun, seed):
    Ms, Fs = [], []
    for i, k in enumerate(ks):
        m, f = stat_MF_(A, k, hfun, seed + i)
        Ms.append(m); Fs.append(f)
    return np.array(Ms), np.array(Fs)

def second_diff(y):
    return np.abs(y[2:] - 2 * y[1:-1] + y[:-2])

def split_anywhere(A, ks, hfun):
    for k in ks:
        lo = mf_relax(A, k, hfun, np.full(M, EPS), 60000).sum()
        hi = mf_relax(A, k, hfun, np.full(M, 12.0), 60000).sum()
        if abs(hi - lo) > 0.5: return True
    return False

ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
t0 = time.time()
arg = sys.argv[1] if len(sys.argv) > 1 else "all"

# ===== Stage A: kappa_c per cyclic graph; degenerate floors =====
if "stageA" not in ck and arg in ("all", "A"):
    kcs = {}
    for sg in CYC:
        edges = edges_seq(M, sg)
        A = adj_at(edges, M, k_cycle(edges, M))
        kcs[sg] = kappa_c(A, h1, h1p)
        print(f"g{sg}: kappa_c^MF = {kcs[sg]:.2f} [{time.time()-t0:.0f}s]", flush=True)
    kbar = float(np.mean(list(kcs.values())))
    deg_grid = list(np.linspace(0.5 * kbar, 1.5 * kbar, NK))
    floors = {"Rc": [], "Rv": [], "absc": []}
    for j, sg in enumerate(DEG):
        edges = edges_seq(M, sg)
        Kc = k_cycle(edges, M)
        A = adj_at(edges, M, max(3, Kc - 2))
        At = rewire_acyclic(A, SEED + sg)
        ks = np.array(deg_grid)
        Md, Fd = curves(A, ks, h1, SEED + sg * 100)
        Mt, Ft = curves(At, ks, h1, SEED + sg * 100 + 50)
        Rc = float(np.max(second_diff(Md)) / max(np.max(second_diff(Mt)), 1e-9))
        Rv = float(np.max(Fd) / max(np.max(Ft), 1e-9))
        aa = [abscissa(A, k, h1, h1p)[0] for k in ks[::3]]
        floors["Rc"].append(Rc); floors["Rv"].append(Rv)
        floors["absc"].append(float(np.max(np.abs(np.array(aa) + 1))))
        print(f"DEG g{sg}: Rc={Rc:.2f} Rv={Rv:.2f} |a+1|max={floors['absc'][-1]:.3f} [{time.time()-t0:.0f}s]", flush=True)
    ck["stageA"] = dict(kappa_c=kcs, deg_grid=deg_grid,
                        floor_c=2.5 * max(floors["Rc"]), floor_v=2.5 * max(floors["Rv"]),
                        deg_absc=floors["absc"], deg_Rc=floors["Rc"], deg_Rv=floors["Rv"])
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"FROZEN: пол_c={ck['stageA']['floor_c']:.2f} пол_v={ck['stageA']['floor_v']:.2f}", flush=True)

if "stageA" in ck and arg not in ("A",):
    SA = ck["stageA"]
    for sg in CYC:
        key = f"g{sg}"
        if key in ck: continue
        if arg != "all" and arg != str(sg): continue
        edges = edges_seq(M, sg)
        A = adj_at(edges, M, k_cycle(edges, M))
        Ad = adj_at(edges, M, k_cycle(edges, M), dag=True)
        kc = SA["kappa_c"][str(sg)]
        ks = np.linspace(0.5 * kc, 1.5 * kc, NK)
        dk = ks[1] - ks[0]
        e = {"kc_mf": kc}
        # h1 main
        Md, Fd = curves(A, ks, h1, SEED + sg * 7)
        Mt, Ft = curves(Ad, ks, h1, SEED + sg * 7 + 3)
        c_d, c_t = second_diff(Md), second_diff(Mt)
        Rc = float(np.max(c_d) / max(np.max(c_t), 1e-9))
        Rv = float(np.max(Fd) / max(np.max(Ft), 1e-9))
        k_hat_c = float(ks[1:-1][np.argmax(c_d)])
        k_hat_v = float(ks[np.argmax(Fd)])
        split1 = split_anywhere(A, ks, h1)
        cons = abs(k_hat_c - k_hat_v) <= 2 * dk + 1e-9
        fires1 = bool(Rc >= SA["floor_c"] and Rv >= SA["floor_v"] and not split1 and cons)
        e["h1"] = dict(Rc=Rc, Rv=Rv, k_c=k_hat_c, k_v=k_hat_v, split=bool(split1),
                       cons=bool(cons), fires=fires1,
                       M=list(Md), F=list(Fd), Mt=list(Mt), Ft=list(Ft), ks=list(ks))
        # h2 cross (same grid scaled to its own regime? prereg: same graphs h=2 -> use ORD windows:
        # frozen: grid = linspace(0.5,1.5)*kc of h1? Prereg says "на h=2 те же графы" with cert legs;
        # use kappa grid around ORD-001 bistable window mid for fairness: [4, 44] fixed span)
        ks2 = np.linspace(4.0, 44.0, NK)
        Md2, Fd2 = curves(A, ks2, h2, SEED + sg * 7 + 5)
        Mt2, Ft2 = curves(Ad, ks2, h2, SEED + sg * 7 + 6)
        Rc2 = float(np.max(second_diff(Md2)) / max(np.max(second_diff(Mt2)), 1e-9))
        Rv2 = float(np.max(Fd2) / max(np.max(Ft2), 1e-9))
        split2 = split_anywhere(A, ks2, h2)
        k2c = float(ks2[1:-1][np.argmax(second_diff(Md2))])
        k2v = float(ks2[np.argmax(Fd2)])
        cons2 = abs(k2c - k2v) <= 2 * (ks2[1] - ks2[0]) + 1e-9
        fires2 = bool(Rc2 >= SA["floor_c"] and Rv2 >= SA["floor_v"] and not split2 and cons2)
        e["h2"] = dict(Rc=Rc2, Rv=Rv2, split=bool(split2), cons=bool(cons2), fires=fires2)
        ck[key] = e
        json.dump(ck, open(CKPT, "w"), default=float)
        print(f"g{sg}: h1 Rc={Rc:.2f} Rv={Rv:.2f} split={split1} cons={cons} fires={fires1} "
              f"(k_c={k_hat_c:.1f}/{k_hat_v:.1f}, kc_mf={kc:.1f}) | h2 Rc={Rc2:.2f} Rv={Rv2:.2f} "
              f"split={split2} fires={fires2} [{time.time()-t0:.0f}s]", flush=True)

if all(f"g{sg}" in ck for sg in CYC):
    SA = ck["stageA"]
    f1 = sum(1 for sg in CYC if ck[f"g{sg}"]["h1"]["fires"])
    f2 = sum(1 for sg in CYC if ck[f"g{sg}"]["h2"]["fires"])
    pq1 = f1 >= 4; pq1_kill = f1 <= 2
    pq2 = f2 == 0; pq2_kill = f2 >= 2
    pq3 = all(a <= 0.05 for a in SA["deg_absc"])
    loc = 0
    for sg in CYC:
        e = ck[f"g{sg}"]
        kc = e["kc_mf"]; dk = kc / 14.0
        khat = 0.5 * (e["h1"]["k_c"] + e["h1"]["k_v"])
        if abs(khat - kc) <= 2 * dk: loc += 1
    pq4 = loc >= 3
    loo = all(sum(1 for j, sg in enumerate(CYC) if j != i and ck[f"g{sg}"]["h1"]["fires"]) >= 3
              for i in range(5))
    ck["verdicts"] = dict(fires_h1=f1, fires_h2=f2, PQ1=bool(pq1), PQ1_killed=bool(pq1_kill),
                          PQ2=bool(pq2), PQ2_killed=bool(pq2_kill), PQ3=bool(pq3),
                          PQ4_n=loc, PQ4=bool(pq4), loo_ok=bool(loo))
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"\nP-Q1: {f1}/5 -> {'ПОДТВЕРЖДЁН' if pq1 else ('УБИТ' if pq1_kill else 'не установлен')} (LOO={loo})")
    print(f"P-Q2: h2 срабатываний {f2}/5 -> {'ПОДТВЕРЖДЁН' if pq2 else ('УБИТ' if pq2_kill else 'не установлен')}")
    print(f"P-Q3 (нильпотентная плоскость): {'подтверждён' if pq3 else 'не подтверждён'} (max {max(SA['deg_absc']):.3f})")
    print(f"P-Q4 (локализация): {loc}/5 -> {'подтверждён' if pq4 else 'не подтверждён'}")
print(f"[{time.time()-t0:.0f}s]")
