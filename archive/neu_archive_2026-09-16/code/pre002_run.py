"""PRE-002 — predictability of birth under preferential growth. Per PREREG (frozen)."""
import json, os, sys, time
import numpy as np

exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])

M = 10
SEED = 20260842
N_PER = 12
N_HOT = 40
STEPS = 10000
REC = 100
CKPT = "/home/claude/pre002_ckpt.json"
UNIF_K = [6, 8, 10]
UNIF_MW_DYN = {6: 0.63, 8: 0.61, 10: 0.77}
UNIF_MW_HAZ = {6: 0.62, 8: 0.64, 10: 0.70}

def pa_edges(seed):
    """Sequential PA edge order: P(i->j) ~ (1+deg_i)(1+deg_j) over remaining pairs."""
    rng = np.random.default_rng(seed)
    deg = np.zeros(M, dtype=np.int64)
    used = np.zeros((M, M), dtype=bool)
    np.fill_diagonal(used, True)
    edges = []
    npairs = M * (M - 1)
    for _ in range(npairs):
        w = np.outer(1 + deg, 1 + deg).astype(float)
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

def kc_of(edges):
    return k_cycle(edges, M)

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

# ===== Stage A: Kc scans and quantile matching =====
if "stageA" not in ck:
    kc_unif = []
    for sg in range(5301, 5901):
        kc = k_cycle(edges_seq(M, sg), M)
        if kc: kc_unif.append(kc)
    kc_pa, pa_cache = [], {}
    for sg in range(6001, 6601):
        e = pa_edges(sg)
        kc = kc_of(e)
        if kc: kc_pa.append(kc); pa_cache[sg] = kc
    kc_unif, kc_pa = np.array(kc_unif), np.array(kc_pa)
    matched = {}
    for K in UNIF_K:
        target = (kc_unif > K).mean()
        cands = np.arange(2, 25)
        surv = np.array([(kc_pa > k).mean() for k in cands])
        matched[K] = int(cands[np.argmin(np.abs(surv - target))])
    ck["stageA"] = dict(matched=matched, med_unif=float(np.median(kc_unif)),
                        med_pa=float(np.median(kc_pa)),
                        mw_kc=mw_auc(kc_unif, kc_pa), pa_kc={str(k): int(v) for k, v in pa_cache.items()})
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"ЭТАП A: согласование K* (униф->PA): {matched}; медианы Kc униф={np.median(kc_unif)} "
          f"PA={np.median(kc_pa)}; MW(Kc_у>Kc_PA)={ck['stageA']['mw_kc']:.2f} [{time.time()-t0:.0f}s]", flush=True)

SA = ck["stageA"]
matched = {int(k): v for k, v in SA["matched"].items()}
pa_kc = {int(k): v for k, v in SA["pa_kc"].items()}

# ===== Stage B: classes + sims per matched K* =====
for K_u in UNIF_K:
    kstar = matched[K_u]
    key = f"K{kstar}"
    if key in ck: continue
    imm, dist = [], []
    for sg in sorted(pa_kc):
        Kc = pa_kc[sg]
        if Kc <= kstar: continue
        d = Kc - kstar
        if d <= 2 and len(imm) < N_PER: imm.append((sg, Kc))
        elif d >= 5 and len(dist) < N_PER: dist.append((sg, Kc))
        if len(imm) >= N_PER and len(dist) >= N_PER: break
    entry = {"K_u": K_u, "kstar": kstar, "imm_n": len(imm), "dist_n": len(dist), "graphs": []}
    print(f"K*_PA={kstar} (пара к униф {K_u}): неминуемых {len(imm)}, далёких {len(dist)}", flush=True)
    for label, group in (("imm", imm), ("dist", dist)):
        for sg, Kc in group:
            edges = pa_edges(sg)
            A = adj_at(edges, M, kstar)
            hi = mf_dark(A).sum() + 6.0
            a = auc_p(A, SEED + sg * 3 + kstar, hi)
            Rp = reach_pairs(A)
            rem = [(i, j) for i in range(M) for j in range(M) if i != j and not A[i, j]]
            closing = sum(1 for (i, j) in rem if Rp[j, i])
            entry["graphs"].append(dict(sg=sg, Kc=Kc, label=label, auc=a,
                                        rho=closing / len(rem), R=int(Rp.sum())))
    ck[key] = entry
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"K*_PA={kstar}: симуляции готовы [{time.time()-t0:.0f}s]", flush=True)

# ===== verdicts =====
if all(f"K{matched[K]}" in ck for K in UNIF_K):
    rng = np.random.default_rng(SEED + 777)
    res, dds, dhz = {}, [], []
    for K_u in UNIF_K:
        e = ck[f"K{matched[K_u]}"]
        g = e["graphs"]
        a1 = [x["auc"] for x in g if x["label"] == "imm"]
        a0 = [x["auc"] for x in g if x["label"] == "dist"]
        r1 = [x["rho"] for x in g if x["label"] == "imm"]
        r0 = [x["rho"] for x in g if x["label"] == "dist"]
        complete = len(a1) >= 8 and len(a0) >= 8
        mwd = mw_auc(a1, a0); mwh = mw_auc(r1, r0)
        allv = np.array(a1 + a0); n1 = len(a1)
        perms = [mw_auc(allv[i[:n1]], allv[i[n1:]]) for i in
                 (rng.permutation(len(allv)) for _ in range(1000))]
        p_perm = float((np.array(perms) >= mwd).mean())
        sp = spear([x["auc"] for x in g], [x["rho"] for x in g])
        res[K_u] = dict(kstar=e["kstar"], complete=bool(complete), n1=len(a1), n0=len(a0),
                        mw_dyn=mwd, p_perm=p_perm, mw_haz=mwh, sp=sp,
                        d_dyn=mwd - UNIF_MW_DYN[K_u], d_haz=mwh - UNIF_MW_HAZ[K_u])
        if complete:
            dds.append(mwd - UNIF_MW_DYN[K_u]); dhz.append(mwh - UNIF_MW_HAZ[K_u])
        print(f"униф K*={K_u} <-> PA K*={e['kstar']} (n={len(a1)}/{len(a0)}): MW_dyn={mwd:.2f} "
              f"(униф {UNIF_MW_DYN[K_u]}; Δ={mwd-UNIF_MW_DYN[K_u]:+.2f}, p={p_perm:.3f}) | "
              f"MW_haz={mwh:.2f} (Δ={mwh-UNIF_MW_HAZ[K_u]:+.2f}) | Спирмен={sp:+.2f}", flush=True)
    comp = [K for K in UNIF_K if res[K]["complete"]]
    dmed = float(np.median(dds))
    pk1 = "a" if dmed >= 0.10 else ("b" if dmed <= -0.10 else "c")
    sps = [res[K]["sp"] for K in comp]
    pk2 = all(s >= 0.8 for s in sps)
    pk2_kill = float(np.median(sps)) < 0.5
    pk3 = (SA["med_pa"] < SA["med_unif"]) and (SA["mw_kc"] >= 0.7)
    dhmed = float(np.median(dhz))
    pk4_h = "a" if dhmed >= 0.10 else ("b" if dhmed <= -0.10 else "c")
    pk4_gap = all(abs(res[K]["mw_dyn"] - res[K]["mw_haz"]) <= 0.10 for K in comp)
    ck["verdicts"] = dict(matched=matched, complete=comp, d_dyn_med=dmed, PK1=pk1,
                          PK2=bool(pk2), PK2_killed=bool(pk2_kill), PK3=bool(pk3),
                          d_haz_med=dhmed, PK4_haz=pk4_h, PK4_gap=bool(pk4_gap), res=res)
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"\nP-K1: медиана Δ_dyn = {dmed:+.2f} -> ветвь ({pk1})")
    print(f"P-K2: Спирмен(AUC,rho) на PA: {[round(s,2) for s in sps]} -> "
          f"{'ПОДТВЕРЖДЁН' if pk2 else ('УБИТ' if pk2_kill else 'не установлен')}")
    print(f"P-K3: медианы Kc {SA['med_unif']} (униф) против {SA['med_pa']} (PA), "
          f"MW={SA['mw_kc']:.2f} -> {'ПОДТВЕРЖДЁН' if pk3 else 'УБИТ'}")
    print(f"P-K4: Δ_haz медиана {dhmed:+.2f} -> ветвь ({pk4_h}); |MW_dyn−MW_haz|<=0.10 всюду: {pk4_gap}")
print(f"[{time.time()-t0:.0f}s]")
