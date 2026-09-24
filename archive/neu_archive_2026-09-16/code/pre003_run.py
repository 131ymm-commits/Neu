"""PRE-003 — alpha-sweep of growth rule. Per PREREG (frozen 2026-08-23)."""
import json, os, sys, time
import numpy as np

exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])

M = 10
SEED = 20260843
N_PER = 12
N_HOT = 40
STEPS = 10000
REC = 100
CKPT = "/home/claude/pre003_ckpt.json"
UNIF_K = [6, 8, 10]
SEED_RANGES = {"0": (7001, 7601), "0.5": (7601, 8201)}
D1_BASE = 0.46  # PRE-002 alpha=1 median MW_dyn

def alpha_edges(seed, alpha):
    rng = np.random.default_rng(seed)
    deg = np.zeros(M, dtype=np.int64)
    used = np.zeros((M, M), dtype=bool)
    np.fill_diagonal(used, True)
    edges = []
    for _ in range(M * (M - 1)):
        w = np.outer(1 + deg, 1 + deg).astype(float) ** alpha
        w[used] = 0.0
        flat = w.ravel()
        s = flat.sum()
        if s <= 0: break
        idx = rng.choice(M * M, p=flat / s)
        i, j = idx // M, idx % M
        used[i, j] = True
        deg[i] += 1; deg[j] += 1
        edges.append((int(i), int(j)))
    return edges

def mf_dark(A):
    n = np.full(M, EPS)
    for _ in range(60000):
        n += 0.01 * (EPS + KAP * (A.T @ hill(n)) - n)
    return n

def auc_p(A, seed, hi):
    rng = np.random.default_rng(seed)
    n = rng.poisson(12.0, size=(N_HOT, M)).astype(float)
    pdeath = 1 - np.exp(-DT)
    Af = A.astype(float)
    ps = []
    for s in range(STEPS):
        b = EPS + KAP * (hill(n) @ Af)
        n = np.clip(n + rng.poisson(b * DT) - rng.binomial(n.astype(np.int64), pdeath), 0, NCAP)
        if (s + 1) % REC == 0:
            ps.append(float((n.sum(1) > hi).mean()))
    return float(np.mean(ps))

def reach_pairs(A):
    R = A.astype(bool).copy()
    for k in range(M):
        R = R | (R[:, k:k+1] & R[k:k+1, :])
    np.fill_diagonal(R, False)
    return R

def mw_auc(x1, x0):
    x1, x0 = np.asarray(x1, float), np.asarray(x0, float)
    gt = (x1[:, None] > x0[None, :]).sum() + 0.5 * (x1[:, None] == x0[None, :]).sum()
    return float(gt / (len(x1) * len(x0)))

def spear(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    rx = np.argsort(np.argsort(x)); ry = np.argsort(np.argsort(y))
    if rx.std() == 0 or ry.std() == 0: return np.nan
    return float(np.corrcoef(rx, ry)[0, 1])

ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
t0 = time.time()
arg = sys.argv[1] if len(sys.argv) > 1 else "all"

# ===== Stage A: scans + matching =====
if "stageA" not in ck:
    kc_unif = np.array([k for k in (k_cycle(edges_seq(M, sg), M) for sg in range(5301, 5901)) if k])
    targets = {K: (kc_unif > K).mean() for K in UNIF_K}
    A_ = {"targets": {str(k): float(v) for k, v in targets.items()}, "arms": {}}
    for al, (s0, s1) in SEED_RANGES.items():
        cache = {}
        for sg in range(s0, s1):
            kc = k_cycle(alpha_edges(sg, float(al)), M)
            if kc: cache[sg] = kc
        kcs = np.array(list(cache.values()))
        matched = {}
        for K in UNIF_K:
            cands = np.arange(2, 25)
            surv = np.array([(kcs > k).mean() for k in cands])
            matched[K] = int(cands[np.argmin(np.abs(surv - targets[K]))])
        A_["arms"][al] = dict(matched={str(k): v for k, v in matched.items()},
                              med_kc=float(np.median(kcs)),
                              kc={str(k): int(v) for k, v in cache.items()})
        print(f"ЭТАП A α={al}: медиана Kc={np.median(kcs)}, согласование {matched} [{time.time()-t0:.0f}s]", flush=True)
    ck["stageA"] = A_
    json.dump(ck, open(CKPT, "w"), default=float)

SA = ck["stageA"]

# ===== Stage B =====
for al in SEED_RANGES:
    if arg != "all" and arg != al: continue
    arm = SA["arms"][al]
    kc_map = {int(k): v for k, v in arm["kc"].items()}
    for K_u in UNIF_K:
        kstar = arm["matched"][str(K_u)]
        key = f"a{al}_K{kstar}_u{K_u}"
        if key in ck: continue
        imm, dist = [], []
        for sg in sorted(kc_map):
            Kc = kc_map[sg]
            if Kc <= kstar: continue
            d = Kc - kstar
            if d <= 2 and len(imm) < N_PER: imm.append((sg, Kc))
            elif d >= 5 and len(dist) < N_PER: dist.append((sg, Kc))
            if len(imm) >= N_PER and len(dist) >= N_PER: break
        entry = {"alpha": al, "K_u": K_u, "kstar": kstar, "graphs": []}
        for label, group in (("imm", imm), ("dist", dist)):
            for sg, Kc in group:
                A = adj_at(alpha_edges(sg, float(al)), M, kstar)
                hi = mf_dark(A).sum() + 6.0
                a = auc_p(A, SEED + sg * 3 + kstar, hi)
                Rp = reach_pairs(A)
                rem = [(i, j) for i in range(M) for j in range(M) if i != j and not A[i, j]]
                closing = sum(1 for (i, j) in rem if Rp[j, i])
                entry["graphs"].append(dict(sg=sg, Kc=Kc, label=label, auc=a, rho=closing / len(rem)))
        ck[key] = entry
        json.dump(ck, open(CKPT, "w"), default=float)
        print(f"α={al} K*={kstar} (униф {K_u}): n={len(imm)}/{len(dist)} готово [{time.time()-t0:.0f}s]", flush=True)

# ===== verdicts =====
done = all(f"a{al}_K{SA['arms'][al]['matched'][str(K)]}_u{K}" in ck
           for al in SEED_RANGES for K in UNIF_K)
if done and arg == "all" or (done and arg == "0.5"):
    rng = np.random.default_rng(SEED + 777)
    res = {}
    for al in SEED_RANGES:
        arm_res = {}
        for K_u in UNIF_K:
            kstar = SA["arms"][al]["matched"][str(K_u)]
            e = ck[f"a{al}_K{kstar}_u{K_u}"]
            g = e["graphs"]
            a1 = [x["auc"] for x in g if x["label"] == "imm"]
            a0 = [x["auc"] for x in g if x["label"] == "dist"]
            complete = len(a1) >= 8 and len(a0) >= 8
            mwd = mw_auc(a1, a0)
            allv = np.array(a1 + a0); n1 = len(a1)
            perms = [mw_auc(allv[i[:n1]], allv[i[n1:]]) for i in
                     (rng.permutation(len(allv)) for _ in range(1000))]
            p_perm = float((np.array(perms) >= mwd).mean())
            sp = spear([x["auc"] for x in g], [x["rho"] for x in g])
            mwh = mw_auc([x["rho"] for x in g if x["label"] == "imm"],
                         [x["rho"] for x in g if x["label"] == "dist"])
            arm_res[K_u] = dict(kstar=kstar, complete=bool(complete), n1=len(a1), n0=len(a0),
                                mw_dyn=mwd, p_perm=p_perm, mw_haz=mwh, sp=sp)
            print(f"α={al} пара {K_u} (K*={kstar}, n={len(a1)}/{len(a0)}): MW_dyn={mwd:.2f} "
                  f"(p={p_perm:.3f}) MW_haz={mwh:.2f} Спирмен={sp:+.2f}", flush=True)
        res[al] = arm_res
    D = {al: float(np.median([res[al][K]["mw_dyn"] for K in UNIF_K if res[al][K]["complete"]]))
         for al in SEED_RANGES}
    D["1"] = D1_BASE
    d0, d05, d1 = D["0"], D["0.5"], D["1"]
    if d0 - d05 >= 0.05 and d05 - d1 >= 0.05: pl1 = "a"
    elif abs(d0 - d05) < 0.05 and d05 - d1 >= 0.10: pl1 = "b"
    elif abs(d05 - d1) < 0.05 and d0 - d05 >= 0.10: pl1 = "c"
    else: pl1 = "не установлен"
    late = res["0"][10]
    pl2 = late["mw_dyn"] >= 0.65 and abs(d0 - 0.63) <= 0.10
    pl2_kill = late["mw_dyn"] <= 0.55
    meds = [SA["arms"]["0"]["med_kc"], SA["arms"]["0.5"]["med_kc"], 7.0]  # 7.0 = PRE-002 PA
    pl3 = (meds[0] >= meds[1] >= meds[2]) and (meds[0] > meds[1] or meds[1] > meds[2])
    pl3_kill = meds[0] < meds[1] or meds[1] < meds[2]
    sps = [res[al][K]["sp"] for al in SEED_RANGES for K in UNIF_K if res[al][K]["complete"]]
    pl4 = all(s >= 0.8 for s in sps)
    pl4_kill = float(np.median(sps)) < 0.5
    ck["verdicts"] = dict(D=D, PL1=pl1, PL2=bool(pl2), PL2_killed=bool(pl2_kill),
                          kc_medians=meds, PL3=bool(pl3), PL3_killed=bool(pl3_kill),
                          PL4=bool(pl4), PL4_killed=bool(pl4_kill), res=res)
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"\nD(α): 0 -> {d0:.2f}, 0.5 -> {d05:.2f}, 1 -> {d1:.2f}")
    print(f"P-L1 (форма): ветвь ({pl1})")
    print(f"P-L2 (репликация): поздняя пара MW={late['mw_dyn']:.2f} -> "
          f"{'ПОДТВЕРЖДЁН' if pl2 else ('УБИТ' if pl2_kill else 'не установлен')}")
    print(f"P-L3 (тайминг): медианы Kc {meds} -> {'ПОДТВЕРЖДЁН' if pl3 else ('УБИТ' if pl3_kill else 'не установлен')}")
    print(f"P-L4 (считывание): {'ПОДТВЕРЖДЁН' if pl4 else ('УБИТ' if pl4_kill else 'не установлен')} "
          f"(min {min(sps):+.2f})")
print(f"[{time.time()-t0:.0f}s]")
