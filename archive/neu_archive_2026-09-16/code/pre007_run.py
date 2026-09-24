"""PRE-007 — localize the alpha suddenness boundary. Per PREREG (frozen 2026-08-26).
Frozen pipeline of PRE-003b: stage-A matching, imm/dist labels, AUC at K*, MW."""
import json, os, sys, time
import numpy as np

exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])

M = 10
SEED = 20260844
N_PER = 24
N_HOT = 40
STEPS = 10000
REC = 100
UNIF_K = [6, 8, 10]
CKPT = "/home/claude/pre007_ckpt.json"
RANGES = {"0.625": (8801, 9401), "0.75": (9401, 10001), "0.875": (10001, 10601)}

def alpha_edges(seed, alpha):
    rng = np.random.default_rng(seed)
    deg = np.zeros(M, dtype=np.int64)
    used = np.zeros((M, M), dtype=bool)
    np.fill_diagonal(used, True)
    edges = []
    for _ in range(M * (M - 1)):
        w = np.outer(1 + deg, 1 + deg).astype(float) ** alpha
        w[used] = 0.0
        flat = w.ravel(); s = flat.sum()
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

def mw_auc(x1, x0):
    x1, x0 = np.asarray(x1, float), np.asarray(x0, float)
    gt = (x1[:, None] > x0[None, :]).sum() + 0.5 * (x1[:, None] == x0[None, :]).sum()
    return float(gt / (len(x1) * len(x0)))

targets = {int(k): float(v) for k, v in
           json.load(open("/home/claude/pre003_ckpt.json"))["stageA"]["targets"].items()}
ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
t0 = time.time()
arg = sys.argv[1] if len(sys.argv) > 1 else "all"

for al, (s0, s1) in RANGES.items():
    if arg != "all" and arg != al: continue
    akey = f"A_{al}"
    if akey not in ck:
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
        ck[akey] = dict(matched=matched, med_kc=float(np.median(kcs)),
                        kc={str(k): int(v) for k, v in cache.items()})
        json.dump(ck, open(CKPT, "w"), default=float)
        print(f"ЭТАП A α={al}: n(Kc)={len(cache)} медиана Kc={np.median(kcs)} согласование {matched} "
              f"[{time.time()-t0:.0f}s]", flush=True)
    A_ = ck[akey]
    for K_u in UNIF_K:
        key = f"b_{al}_u{K_u}"
        if key in ck: continue
        kstar = A_["matched"][str(K_u)] if isinstance(A_["matched"], dict) and str(K_u) in A_["matched"] else A_["matched"][K_u]
        counts = {"imm": 0, "dist": 0}
        graphs = []
        for sg in sorted(int(x) for x in A_["kc"]):
            if counts["imm"] >= N_PER and counts["dist"] >= N_PER: break
            Kc = A_["kc"][str(sg)]
            if Kc <= kstar: continue
            d = Kc - kstar
            lab = "imm" if d <= 2 else ("dist" if d >= 5 else None)
            if lab and counts[lab] < N_PER:
                counts[lab] += 1
                Am = adj_at(alpha_edges(sg, float(al)), M, kstar)
                hi = mf_dark(Am).sum() + 6.0
                a = auc_p(Am, SEED + sg * 3 + kstar, hi)
                graphs.append(dict(sg=sg, Kc=Kc, label=lab, auc=a))
        ck[key] = dict(kstar=kstar, n_imm=counts["imm"], n_dist=counts["dist"], graphs=graphs)
        json.dump(ck, open(CKPT, "w"), default=float)
        print(f"α={al} пара {K_u} (K*={kstar}): {counts['imm']}/{counts['dist']} [{time.time()-t0:.0f}s]", flush=True)

if all(f"b_{al}_u{K}" in ck for al in RANGES for K in UNIF_K):
    rng = np.random.default_rng(SEED + 778)
    D, res = {}, {}
    for al in RANGES:
        mws = []
        for K_u in UNIF_K:
            e = ck[f"b_{al}_u{K_u}"]
            a1 = [x["auc"] for x in e["graphs"] if x["label"] == "imm"]
            a0 = [x["auc"] for x in e["graphs"] if x["label"] == "dist"]
            complete = len(a1) >= 16 and len(a0) >= 16
            mwd = mw_auc(a1, a0)
            allv = np.array(a1 + a0); n1 = len(a1)
            perms = [mw_auc(allv[i[:n1]], allv[i[n1:]]) for i in
                     (rng.permutation(len(allv)) for _ in range(1000))]
            p_perm = float((np.array(perms) >= mwd).mean())
            res[f"{al}|{K_u}"] = dict(n1=len(a1), n0=len(a0), complete=bool(complete), mw=mwd, p=p_perm)
            if complete: mws.append(mwd)
            print(f"α={al} пара {K_u}: n={len(a1)}/{len(a0)} MW={mwd:.3f} (p={p_perm:.3f})", flush=True)
        D[al] = float(np.median(mws)) if mws else None
    # five-point curve with anchors
    curve = {"0.5": 0.6918402777777778, **{al: D[al] for al in RANGES}, "1": 0.5182291666666666}
    xs = [0.5, 0.625, 0.75, 0.875, 1.0]
    ys = [curve["0.5"], curve["0.625"], curve["0.75"], curve["0.875"], curve["1"]]
    DMID = 0.605
    alpha_b = None
    for i in range(len(xs) - 1):
        y1, y2 = ys[i], ys[i + 1]
        if (y1 >= DMID) and (y2 < DMID):
            alpha_b = xs[i] + (xs[i + 1] - xs[i]) * (y1 - DMID) / (y1 - y2)
            break
    if alpha_b is None:
        alpha_b = 0.9375 if all(y >= DMID for y in ys[1:-1]) else 0.5625  # (0.875,1] mid / below-grid marker
    grow = max(ys[i + 1] - ys[i] for i in range(len(xs) - 1))
    pl1 = grow <= 0.03
    pl1_kill = grow >= 0.10
    pl2 = alpha_b >= 0.75
    pl2_kill = alpha_b <= 0.625
    meds = {al: ck[f"A_{al}"]["med_kc"] for al in RANGES}
    pl3 = meds["0.625"] >= meds["0.75"] >= meds["0.875"]
    ck["verdicts"] = dict(D=D, curve=dict(zip(map(str, xs), ys)), alpha_b=float(alpha_b),
                          max_growth=float(grow), PL1=bool(pl1), PL1_killed=bool(pl1_kill),
                          PL2=bool(pl2), PL2_killed=bool(pl2_kill), med_kc=meds, PL3=bool(pl3), res=res)
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"\nКривая D(α): " + " ".join(f"{x}:{y:.3f}" for x, y in zip(xs, ys)))
    print(f"α_b (уровень {DMID}) = {alpha_b:.3f}")
    print(f"P-L1 (монотонность, макс. рост {grow:+.3f}): {'ПОДТВЕРЖДЁН' if pl1 else ('УБИТ' if pl1_kill else 'не установлен')}")
    print(f"P-L2 (α_b >= 0.75): {'ПОДТВЕРЖДЁН' if pl2 else ('УБИТ' if pl2_kill else 'не установлен')}")
    print(f"P-L3 (медианы Kc убывают): {pl3} ({meds})")
print(f"[{time.time()-t0:.0f}s]")
