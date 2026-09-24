"""PRE-003b — resolve D(alpha) at n=24+24. Per PREREG. Reuses sims from pre002/pre003 ckpts."""
import json, os, sys, time
import numpy as np

exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])

M = 10
SEED = 20260844
N_PER = 24
N_HOT = 40
STEPS = 10000
REC = 100
CKPT = "/home/claude/pre003b_ckpt.json"
UNIF_K = [6, 8, 10]

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

ck3 = json.load(open("/home/claude/pre003_ckpt.json"))
ck2 = json.load(open("/home/claude/pre002_ckpt.json"))
ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
t0 = time.time()
arg = sys.argv[1] if len(sys.argv) > 1 else "all"

# per-arm: kc cache, matched kstar per uniform K, existing simulated graphs
ARMS = {}
for al in ("0", "0.5"):
    arm = ck3["stageA"]["arms"][al]
    ARMS[al] = dict(kc={int(k): int(v) for k, v in arm["kc"].items()},
                    matched={int(k): int(v) for k, v in arm["matched"].items()},
                    existing={int(K): ck3[f"a{al}_K{arm['matched'][str(K)]}_u{K}"]["graphs"]
                              for K in UNIF_K},
                    gen=lambda sg, a=float(al): alpha_edges(sg, a))
pa_kc = {int(k): int(v) for k, v in ck2["stageA"]["pa_kc"].items()}
ARMS["1"] = dict(kc=pa_kc,
                 matched={int(k): int(v) for k, v in ck2["verdicts"]["matched"].items()},
                 existing={int(K): ck2[f"K{ck2['verdicts']['matched'][str(K)]}"]["graphs"]
                           for K in UNIF_K},
                 gen=lambda sg: alpha_edges(sg, 1.0))

# extend alpha=1 kc scan if needed
if "kc1ext" not in ck:
    ext = {}
    for sg in range(8201, 8801):
        kc = k_cycle(alpha_edges(sg, 1.0), M)
        if kc: ext[sg] = kc
    ck["kc1ext"] = {str(k): v for k, v in ext.items()}
    json.dump(ck, open(CKPT, "w"), default=float)
ARMS["1"]["kc"] = {**ARMS["1"]["kc"], **{int(k): int(v) for k, v in ck["kc1ext"].items()}}

for al, arm in ARMS.items():
    if arg != "all" and arg != al: continue
    for K_u in UNIF_K:
        kstar = arm["matched"][K_u]
        key = f"b_a{al}_u{K_u}"
        if key in ck: continue
        have = {g["sg"] for g in arm["existing"][K_u]}
        counts = {"imm": sum(1 for g in arm["existing"][K_u] if g["label"] == "imm"),
                  "dist": sum(1 for g in arm["existing"][K_u] if g["label"] == "dist")}
        new = []
        for sg in sorted(arm["kc"]):
            if counts["imm"] >= N_PER and counts["dist"] >= N_PER: break
            if sg in have: continue
            Kc = arm["kc"][sg]
            if Kc <= kstar: continue
            d = Kc - kstar
            lab = "imm" if d <= 2 else ("dist" if d >= 5 else None)
            if lab and counts[lab] < N_PER:
                counts[lab] += 1
                new.append((sg, Kc, lab))
        graphs = list(arm["existing"][K_u])
        for sg, Kc, lab in new:
            A = adj_at(arm["gen"](sg), M, kstar)
            hi = mf_dark(A).sum() + 6.0
            a = auc_p(A, SEED + sg * 3 + kstar, hi)
            graphs.append(dict(sg=sg, Kc=Kc, label=lab, auc=a))
        ck[key] = dict(kstar=kstar, n_imm=counts["imm"], n_dist=counts["dist"], graphs=graphs)
        json.dump(ck, open(CKPT, "w"), default=float)
        print(f"α={al} пара {K_u} (K*={kstar}): {counts['imm']}/{counts['dist']} "
              f"(+{len(new)} новых) [{time.time()-t0:.0f}s]", flush=True)

if all(f"b_a{al}_u{K}" in ck for al in ARMS for K in UNIF_K):
    rng = np.random.default_rng(SEED + 777)
    D, res = {}, {}
    for al in ARMS:
        mws = []
        for K_u in UNIF_K:
            e = ck[f"b_a{al}_u{K_u}"]
            a1 = [x["auc"] for x in e["graphs"] if x["label"] == "imm"]
            a0 = [x["auc"] for x in e["graphs"] if x["label"] == "dist"]
            complete = len(a1) >= 16 and len(a0) >= 16
            mwd = mw_auc(a1, a0)
            allv = np.array(a1 + a0); n1 = len(a1)
            perms = [mw_auc(allv[i[:n1]], allv[i[n1:]]) for i in
                     (rng.permutation(len(allv)) for _ in range(1000))]
            p_perm = float((np.array(perms) >= mwd).mean())
            res[f"{al}|{K_u}"] = dict(n1=len(a1), n0=len(a0), complete=bool(complete),
                                      mw=mwd, p=p_perm)
            if complete: mws.append(mwd)
            print(f"α={al} пара {K_u}: n={len(a1)}/{len(a0)} MW={mwd:.2f} (p={p_perm:.3f})", flush=True)
        D[al] = float(np.median(mws)) if mws else None
    d0, d05, d1 = D["0"], D["0.5"], D["1"]
    pm1 = (d05 - d1 >= 0.10)
    pm1_kill = (d05 - d1 < 0.05)
    pm2 = (d0 - d1 >= 0.10)
    pm2_kill = (d0 - d1 < 0.05)
    pm3 = bool(d05 > d0)
    ck["verdicts"] = dict(D=D, PM1=bool(pm1), PM1_killed=bool(pm1_kill),
                          PM2=bool(pm2), PM2_killed=bool(pm2_kill), PM3_nonmono=pm3, res=res)
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"\nD(α) при n=24: 0 -> {d0:.2f}, 0.5 -> {d05:.2f}, 1 -> {d1:.2f}")
    print(f"P-M1: {'ПОДТВЕРЖДЁН' if pm1 else ('УБИТ' if pm1_kill else 'не установлен')} (Δ={d05-d1:+.2f})")
    print(f"P-M2: {'ПОДТВЕРЖДЁН' if pm2 else ('УБИТ' if pm2_kill else 'не установлен')} (Δ={d0-d1:+.2f})")
    print(f"P-M3: немонотонность D(0.5)>D(0) при n=24: {pm3}")
print(f"[{time.time()-t0:.0f}s]")
