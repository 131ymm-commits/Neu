"""PRE-001b — does dynamics read closure proximity at fixed K? Per PREREG (frozen)."""
import json, os, sys, time
import numpy as np

exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])

M = 10
SEED = 20260841
KSTARS = [6, 8, 10]
N_PER = 12
N_HOT = 40
STEPS = 10000
REC = 100
CKPT = "/home/claude/pre001b_ckpt.json"

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

def rewire_acyclic(A, seed, attempts=200):
    rng = np.random.default_rng(seed)
    B = A.copy()
    for _ in range(attempts):
        es = np.argwhere(B == 1)
        if len(es) < 2: break
        i1, i2 = rng.choice(len(es), 2, replace=False)
        (a, b), (c, d) = es[i1], es[i2]
        if a == d or c == b or B[a, d] or B[c, b]: continue
        B2 = B.copy()
        B2[a, b] = 0; B2[c, d] = 0; B2[a, d] = 1; B2[c, b] = 1
        if not has_cycle(B2, M):
            B = B2
    return B

def mw_auc(x1, x0):
    """P(x1 > x0) rank-based; x1 = imminent, x0 = distant."""
    x1, x0 = np.asarray(x1, float), np.asarray(x0, float)
    gt = (x1[:, None] > x0[None, :]).sum() + 0.5 * (x1[:, None] == x0[None, :]).sum()
    return float(gt / (len(x1) * len(x0)))

def spear(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    rx = np.argsort(np.argsort(x)); ry = np.argsort(np.argsort(y))
    if rx.std() == 0 or ry.std() == 0: return np.nan
    return float(np.corrcoef(rx, ry)[0, 1])

# ---- selection scan (deterministic order, no hand-picking) ----
def select(kstar):
    imm, dist = [], []
    for sg in range(5301, 5901):
        if len(imm) >= N_PER and len(dist) >= N_PER: break
        edges = edges_seq(M, sg)
        Kc = k_cycle(edges, M)
        if Kc is None or Kc <= kstar: continue
        d = Kc - kstar
        if d <= 2 and len(imm) < N_PER: imm.append((sg, Kc))
        elif d >= 5 and len(dist) < N_PER: dist.append((sg, Kc))
    return imm, dist

ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
t0 = time.time()
arg = sys.argv[1] if len(sys.argv) > 1 else "all"

for kstar in KSTARS:
    key = str(kstar)
    if arg != "all" and key != arg: continue
    if key in ck: continue
    imm, dist = select(kstar)
    entry = {"imm_n": len(imm), "dist_n": len(dist), "graphs": []}
    print(f"K*={kstar}: неминуемых {len(imm)}, далёких {len(dist)} [{time.time()-t0:.0f}s]", flush=True)
    for label, group in (("imm", imm), ("dist", dist)):
        for sg, Kc in group:
            edges = edges_seq(M, sg)
            A = adj_at(edges, M, kstar)
            hi = mf_dark(A).sum() + 6.0
            a_data = auc_p(A, SEED + sg * 3 + kstar, hi)
            At = rewire_acyclic(A, SEED + sg * 3 + kstar + 1)
            a_twin = auc_p(At, SEED + sg * 3 + kstar + 2, mf_dark(At).sum() + 6.0)
            Rp = reach_pairs(A)
            rem = [(i, j) for i in range(M) for j in range(M) if i != j and not A[i, j]]
            closing = sum(1 for (i, j) in rem if Rp[j, i])
            entry["graphs"].append(dict(sg=sg, Kc=Kc, label=label, auc=a_data, auc_twin=a_twin,
                                        rho=closing / len(rem), R=int(Rp.sum())))
    ck[key] = entry
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"K*={kstar}: симуляции готовы [{time.time()-t0:.0f}s]", flush=True)

if all(str(k) in ck for k in KSTARS):
    rng = np.random.default_rng(SEED + 777)
    res = {}
    for kstar in KSTARS:
        e = ck[str(kstar)]
        g = e["graphs"]
        a1 = [x["auc"] for x in g if x["label"] == "imm"]
        a0 = [x["auc"] for x in g if x["label"] == "dist"]
        t1 = [x["auc_twin"] for x in g if x["label"] == "imm"]
        t0_ = [x["auc_twin"] for x in g if x["label"] == "dist"]
        r1 = [x["rho"] for x in g if x["label"] == "imm"]
        r0 = [x["rho"] for x in g if x["label"] == "dist"]
        complete = len(a1) >= 8 and len(a0) >= 8
        auc_d = mw_auc(a1, a0)
        # permutation p
        allv = np.array(a1 + a0); n1 = len(a1)
        perms = []
        for _ in range(1000):
            idx = rng.permutation(len(allv))
            perms.append(mw_auc(allv[idx[:n1]], allv[idx[n1:]]))
        p_perm = float((np.array(perms) >= auc_d).mean())
        # LOO
        pooled = [(v, 1) for v in a1] + [(v, 0) for v in a0]
        loo_min = min(
            mw_auc([v for j, (v, l) in enumerate(pooled) if l == 1 and j != i],
                   [v for j, (v, l) in enumerate(pooled) if l == 0 and j != i])
            for i in range(len(pooled)))
        auc_twin = mw_auc(t1, t0_)
        auc_rho = mw_auc(r1, r0)
        sp = spear([x["auc"] for x in g], [x["rho"] for x in g])
        res[kstar] = dict(complete=bool(complete), n1=len(a1), n0=len(a0), mw=auc_d,
                          p_perm=p_perm, loo_min=float(loo_min), mw_twin=auc_twin,
                          mw_rho=auc_rho, sp_rho=sp)
        print(f"K*={kstar} (n={len(a1)}/{len(a0)}): MW={auc_d:.2f} (p={p_perm:.3f}, LOO min {loo_min:.2f}) | "
              f"твин {auc_twin:.2f} | rho-MW {auc_rho:.2f} | Спирмен(AUC,rho)={sp:+.2f}", flush=True)
    comp = [k for k in KSTARS if res[k]["complete"]]
    pj1_hits = sum(1 for k in comp if res[k]["mw"] >= 0.70 and res[k]["p_perm"] <= 0.05)
    pj1 = pj1_hits >= 2
    pj1_kill = all(res[k]["mw"] <= 0.55 for k in comp) if comp else False
    pj2_hits = sum(1 for k in comp if res[k]["sp_rho"] >= 0.5)
    pj2 = pj2_hits >= 2
    pj2_kill = (np.median([res[k]["sp_rho"] for k in comp]) <= 0) if comp else False
    pj3 = sum(1 for k in comp if res[k]["mw_rho"] >= 0.8)
    drops = [res[k]["mw"] - res[k]["mw_twin"] for k in comp]
    pj4 = "a" if np.median(drops) >= 0.15 else "b"
    ck["verdicts"] = dict(complete_K=comp, PJ1=bool(pj1), PJ1_hits=pj1_hits, PJ1_killed=bool(pj1_kill),
                          PJ2=bool(pj2), PJ2_killed=bool(pj2_kill), PJ3_hits=pj3,
                          PJ4=pj4, twin_drop_median=float(np.median(drops)), res=res)
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"\nПолные K*: {comp}")
    print(f"P-J1: {'ПОДТВЕРЖДЁН' if pj1 else ('УБИТ' if pj1_kill else 'не установлен')} ({pj1_hits}/{len(comp)} K* с MW>=0.70 и p<=0.05)")
    print(f"P-J2: {'ПОДТВЕРЖДЁН' if pj2 else ('УБИТ' if pj2_kill else 'не установлен')} ({pj2_hits}/{len(comp)})")
    print(f"P-J3 (санити): rho-MW >= 0.8 в {pj3}/{len(comp)}")
    print(f"P-J4: исход ({pj4}), медианное падение на твинах {np.median(drops):+.2f}")
print(f"[{time.time()-t0:.0f}s]")
