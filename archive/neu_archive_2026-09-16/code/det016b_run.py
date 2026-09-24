"""DET-016b — continuous-birth certificate v2. Per PREREG (frozen 2026-08-24)."""
import json, os, sys, time
import numpy as np

exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])

M = 10
SEED = 20260848
CYC = [5201, 5202, 5203, 5204, 5205]
DEG = [5206, 5207, 5208]
NK = 15
N_TR = 64
T_ST = 120.0
STEPS = int(T_ST / DT)
BURN = int(0.3 * (STEPS // 100))
CKPT = "/home/claude/det016b_ckpt.json"
KCMF = {"5201": 2.97, "5202": 3.95, "5203": 2.97, "5204": 3.95, "5205": 2.64}

def h1(n): return n / (4.0 + n)
def h2(n): return n * n / (16.0 + n * n)

def mf_relax(A, kap, hfun, n0, steps=30000):
    n = n0.copy()
    for _ in range(steps):
        n += 0.01 * (EPS + kap * (A.T @ hfun(n)) - n)
    return n

def stat_MF_(A, kap, hfun, seed, ntr=N_TR, steps=STEPS, burn=BURN):
    rng = np.random.default_rng(seed)
    nd = mf_relax(A, kap, hfun, np.full(M, EPS))
    n = rng.poisson(np.maximum(nd, 0), size=(ntr, M)).astype(float)
    pdeath = 1 - np.exp(-DT)
    Af = A.astype(float)
    tot = []
    for s in range(steps):
        b = EPS + kap * (hfun(n) @ Af)
        n = np.clip(n + rng.poisson(b * DT) - rng.binomial(n.astype(np.int64), pdeath), 0, NCAP)
        if (s + 1) % 100 == 0:
            tot.append(n.sum(1).copy())
    X = np.array(tot)[burn:]
    means = X.mean(0); varis = X.var(0)
    return float(np.median(means)), float(np.median(varis / np.maximum(means, 1e-9)))

def curves(A, ks, hfun, seed, **kw):
    Ms, Fs = [], []
    for i, k in enumerate(ks):
        m, f = stat_MF_(A, k, hfun, seed + i, **kw)
        Ms.append(m); Fs.append(f)
    return np.array(Ms), np.array(Fs)

def kink_fit(ks, Ms):
    """Two-segment least-squares; returns |slope2-slope1| and breakpoint kappa."""
    best = (0.0, None)
    for bi in range(3, len(ks) - 3):
        x1, y1 = ks[:bi + 1], Ms[:bi + 1]
        x2, y2 = ks[bi:], Ms[bi:]
        s1 = np.polyfit(x1, y1, 1)[0]
        s2 = np.polyfit(x2, y2, 1)[0]
        r1 = np.sum((y1 - np.polyval(np.polyfit(x1, y1, 1), x1)) ** 2)
        r2 = np.sum((y2 - np.polyval(np.polyfit(x2, y2, 1), x2)) ** 2)
        # choose breakpoint minimizing residual; strength from that fit
        best = min(best, (r1 + r2, (abs(s2 - s1), float(ks[bi]))), key=lambda t: t[0]) \
            if best[1] is not None else (r1 + r2, (abs(s2 - s1), float(ks[bi])))
    return best[1]

def prescan_kf(A, kcmf, hfun, seed):
    ks = np.linspace(0.5 * kcmf, 3.0 * kcmf, 9)
    _, Fs = curves(A, ks, hfun, seed, ntr=16, steps=int(60.0 / DT), burn=int(0.3 * 60))
    i = int(np.argmax(Fs))
    if i == len(ks) - 1:                       # edge -> extend once
        ks = np.linspace(0.5 * kcmf, 4.5 * kcmf, 9)
        _, Fs = curves(A, ks, hfun, seed + 100, ntr=16, steps=int(60.0 / DT), burn=int(0.3 * 60))
        i = int(np.argmax(Fs))
    return float(ks[i])

def split_anywhere(A, ks, hfun):
    for k in ks:
        lo = mf_relax(A, k, hfun, np.full(M, EPS), 60000).sum()
        hi = mf_relax(A, k, hfun, np.full(M, 12.0), 60000).sum()
        if abs(hi - lo) > 0.5: return True
    return False

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

ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
t0 = time.time()
arg = sys.argv[1] if len(sys.argv) > 1 else "all"

# ===== Stage A': degenerate floors with new estimators =====
if "floors" not in ck and arg in ("all", "A"):
    kbar = float(np.mean(list(KCMF.values())))
    Rcs, Rvs = [], []
    for sg in DEG:
        edges = edges_seq(M, sg)
        Kc = k_cycle(edges, M)
        A = adj_at(edges, M, max(3, Kc - 2))
        At = rewire_acyclic(A, SEED + sg)
        kf = prescan_kf(A, kbar, h1, SEED + sg * 100)
        ks = np.linspace(0.5 * kf, 1.6 * kf, NK)
        Md, Fd = curves(A, ks, h1, SEED + sg * 100 + 20)
        Mt, Ft = curves(At, ks, h1, SEED + sg * 100 + 40)
        kd, _ = kink_fit(ks, Md)
        kt, _ = kink_fit(ks, Mt)
        Rc = kd / max(kt, 1e-9)
        Rv = float(np.max(Fd) / max(np.max(Ft), 1e-9))
        Rcs.append(Rc); Rvs.append(Rv)
        print(f"DEG g{sg}: Rc={Rc:.2f} Rv={Rv:.2f} (kf={kf:.1f}) [{time.time()-t0:.0f}s]", flush=True)
    ck["floors"] = dict(floor_c=2.5 * max(Rcs), floor_v=2.5 * max(Rvs), deg_Rc=Rcs, deg_Rv=Rvs)
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"FROZEN v2: пол_c={ck['floors']['floor_c']:.2f} пол_v={ck['floors']['floor_v']:.2f}", flush=True)

if "floors" in ck and arg not in ("A",):
    FL = ck["floors"]
    for sg in CYC:
        key = f"g{sg}"
        if key in ck: continue
        if arg != "all" and arg != str(sg): continue
        edges = edges_seq(M, sg)
        A = adj_at(edges, M, k_cycle(edges, M))
        Ad = adj_at(edges, M, k_cycle(edges, M), dag=True)
        kf = prescan_kf(A, KCMF[str(sg)], h1, SEED + sg * 3)
        ks = np.linspace(0.5 * kf, 1.6 * kf, NK)
        dk = ks[1] - ks[0]
        Md, Fd = curves(A, ks, h1, SEED + sg * 3 + 1)
        Mt, Ft = curves(Ad, ks, h1, SEED + sg * 3 + 2)
        kd, kbp = kink_fit(ks, Md)
        kt, _ = kink_fit(ks, Mt)
        Rc = kd / max(kt, 1e-9)
        iF = int(np.argmax(Fd))
        Rv = float(np.max(Fd) / max(np.max(Ft), 1e-9))
        interior = 0 < iF < NK - 1
        k_v = float(ks[iF])
        split1 = split_anywhere(A, ks, h1)
        cons = abs(kbp - k_v) <= 3 * dk + 1e-9
        fires = bool(Rc >= FL["floor_c"] and Rv >= FL["floor_v"] and not split1 and cons and interior)
        e = dict(kf=kf, Rc=Rc, Rv=Rv, kbp=kbp, k_v=k_v, interior=bool(interior),
                 split=bool(split1), cons=bool(cons), fires=fires,
                 ks=list(ks), M=list(Md), F=list(Fd), Mt=list(Mt), Ft=list(Ft))
        # h2 cross with same estimators (own prescan on h2)
        kf2 = prescan_kf(A, 20.0, h2, SEED + sg * 3 + 7)
        ks2 = np.linspace(0.5 * kf2, 1.6 * kf2, NK)
        Md2, Fd2 = curves(A, ks2, h2, SEED + sg * 3 + 8)
        Mt2, Ft2 = curves(Ad, ks2, h2, SEED + sg * 3 + 9)
        kd2, kbp2 = kink_fit(ks2, Md2)
        kt2, _ = kink_fit(ks2, Mt2)
        Rc2 = kd2 / max(kt2, 1e-9)
        iF2 = int(np.argmax(Fd2))
        Rv2 = float(np.max(Fd2) / max(np.max(Ft2), 1e-9))
        split2 = split_anywhere(A, ks2, h2)
        cons2 = abs(kbp2 - float(ks2[iF2])) <= 3 * (ks2[1] - ks2[0]) + 1e-9
        fires2 = bool(Rc2 >= FL["floor_c"] and Rv2 >= FL["floor_v"] and not split2 and cons2
                      and 0 < iF2 < NK - 1)
        e["h2"] = dict(Rc=Rc2, Rv=Rv2, split=bool(split2), fires=fires2)
        ck[key] = e
        json.dump(ck, open(CKPT, "w"), default=float)
        print(f"g{sg}: v2 Rc={Rc:.2f} Rv={Rv:.2f} split={split1} cons={cons} int={interior} "
              f"fires={fires} (kf={kf:.1f}, kbp={kbp:.1f}, k_v={k_v:.1f}) | "
              f"h2 fires={fires2} (split={split2}) [{time.time()-t0:.0f}s]", flush=True)

if all(f"g{sg}" in ck for sg in CYC):
    FL = ck["floors"]
    f1 = sum(1 for sg in CYC if ck[f"g{sg}"]["fires"])
    f2 = sum(1 for sg in CYC if ck[f"g{sg}"]["h2"]["fires"])
    pr1 = f1 >= 4; pr1_kill = f1 <= 2
    pr2 = f2 == 0; pr2_kill = f2 >= 2
    loc = sum(1 for sg in CYC
              if abs(0.5 * (ck[f"g{sg}"]["kbp"] + ck[f"g{sg}"]["k_v"]) - ck[f"g{sg}"]["kf"]) <=
              3 * (ck[f"g{sg}"]["ks"][1] - ck[f"g{sg}"]["ks"][0]))
    pr3 = loc >= 3
    loo = all(sum(1 for j, sg in enumerate(CYC) if j != i and ck[f"g{sg}"]["fires"]) >= 3
              for i in range(5))
    ck["verdicts"] = dict(fires_h1=f1, fires_h2=f2, PR1=bool(pr1), PR1_killed=bool(pr1_kill),
                          PR2=bool(pr2), PR2_killed=bool(pr2_kill), PR3_n=loc, PR3=bool(pr3),
                          loo_ok=bool(loo))
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"\nP-R1: {f1}/5 -> {'ПОДТВЕРЖДЁН' if pr1 else ('УБИТ' if pr1_kill else 'не установлен')} (LOO={loo})")
    print(f"P-R2: h2 {f2}/5 -> {'ПОДТВЕРЖДЁН' if pr2 else ('УБИТ' if pr2_kill else 'не установлен')}")
    print(f"P-R3 (локализация): {loc}/5 -> {'подтверждён' if pr3 else 'не подтверждён'}")
print(f"[{time.time()-t0:.0f}s]")
