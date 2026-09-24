"""PRE-009 — horizon curve MW(d). Per PREREG (frozen 2026-08-26).
Stored AUCs from pre003b ckpt + fill d in {3,4} with the same pipeline."""
import json, os, time
import numpy as np

exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])

M = 10
SEED = 20260844
N_HOT = 40
STEPS = 10000
REC = 100
N_FILL = 8
CKPT = "/home/claude/pre009_ckpt.json"

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

def mw(x1, x0):
    x1, x0 = np.asarray(x1, float), np.asarray(x0, float)
    gt = (x1[:, None] > x0[None, :]).sum() + 0.5 * (x1[:, None] == x0[None, :]).sum()
    return float(gt / (len(x1) * len(x0)))

ck3b = json.load(open("/home/claude/pre003b_ckpt.json"))
ck3 = json.load(open("/home/claude/pre003_ckpt.json"))
ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
t0 = time.time()
CELLS = [(al, K) for al in ("0", "0.5") for K in (6, 8, 10)]

# ---------- fill d=3,4 ----------
for al, K in CELLS:
    key = f"fill_{al}_{K}"
    if key in ck: continue
    e = ck3b[f"b_a{al}_u{K}"]
    ks = e["kstar"]
    have = {g["sg"] for g in e["graphs"]}
    kc = {int(k): int(v) for k, v in ck3["stageA"]["arms"][al]["kc"].items()}
    new = []
    counts = {3: 0, 4: 0}
    for sg in sorted(kc):
        if counts[3] >= N_FILL and counts[4] >= N_FILL: break
        if sg in have: continue
        d = kc[sg] - ks
        if d in (3, 4) and counts[d] < N_FILL:
            counts[d] += 1
            A = adj_at(alpha_edges(sg, float(al)), M, ks)
            hi = mf_dark(A).sum() + 6.0
            a = auc_p(A, SEED + sg * 3 + ks, hi)
            new.append(dict(sg=sg, Kc=kc[sg], d=d, auc=a))
    ck[key] = dict(kstar=ks, graphs=new)
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"α={al} K_u={K}: заполнено d3={counts[3]} d4={counts[4]} [{time.time()-t0:.0f}s]", flush=True)

# ---------- stratified curve ----------
rng = np.random.default_rng(SEED + 779)
cells = {}
for al, K in CELLS:
    e = ck3b[f"b_a{al}_u{K}"]
    ks = e["kstar"]
    binsd = {d: [] for d in range(1, 7)}
    ref = []
    for g in e["graphs"]:
        d = g["Kc"] - ks
        if 1 <= d <= 6: binsd[d].append(g["auc"])
        elif d >= 7: ref.append(g["auc"])
    for g in ck[f"fill_{al}_{K}"]["graphs"]:
        binsd[g["d"]].append(g["auc"])
    cells[(al, K)] = (binsd, ref)

def curve(cell_keys):
    out = {}
    for d in range(1, 7):
        num = den = 0.0
        for ckey in cell_keys:
            binsd, ref = cells[ckey]
            if len(binsd[d]) >= 4 and len(ref) >= 4:
                w = min(len(binsd[d]), len(ref))
                num += w * mw(binsd[d], ref); den += w
        out[d] = num / den if den else None
    return out

MWd = curve(CELLS)
# permutation p for d=1 and d=6 (within-cell label permutation)
def perm_p(d, n=1000):
    obs = MWd[d]
    cnt = 0
    for _ in range(n):
        num = den = 0.0
        for ckey in CELLS:
            binsd, ref = cells[ckey]
            if len(binsd[d]) >= 4 and len(ref) >= 4:
                pool = np.array(binsd[d] + ref)
                idx = rng.permutation(len(pool))
                x1 = pool[idx[:len(binsd[d])]]; x0 = pool[idx[len(binsd[d]):]]
                w = min(len(binsd[d]), len(ref))
                num += w * mw(x1, x0); den += w
        if den and num / den >= obs: cnt += 1
    return cnt / n

p1, p6 = perm_p(1), perm_p(6)
vals = [MWd[d] for d in range(1, 7)]
grow = max((vals[i + 1] - vals[i]) for i in range(5) if vals[i] is not None and vals[i + 1] is not None)
ph1 = grow <= 0.04; ph1_kill = grow >= 0.10
dh = next((d for d in range(1, 7) if MWd[d] is not None and MWd[d] <= 0.55), None)
ph2 = dh is not None and 3 <= dh <= 6
ph2_kill = (MWd[1] is not None and MWd[1] <= 0.55) or (MWd[6] is not None and MWd[6] >= 0.65)
ph3 = MWd[1] is not None and MWd[1] >= 0.65
# LOO over cells
loo = []
for drop in CELLS:
    sub = [c for c in CELLS if c != drop]
    cv = curve(sub)
    dh_s = next((d for d in range(1, 7) if cv[d] is not None and cv[d] <= 0.55), None)
    loo.append(dict(drop=f"{drop[0]}|{drop[1]}", mw1=cv[1], dh=dh_s))
ck["curve"] = {str(d): MWd[d] for d in MWd}
ck["verdicts"] = dict(MWd={str(d): MWd[d] for d in MWd}, p1=p1, p6=p6, max_growth=float(grow),
                      PH1=bool(ph1), PH1_killed=bool(ph1_kill), d_h=dh, PH2=bool(ph2),
                      PH2_killed=bool(ph2_kill), PH3=bool(ph3), loo=loo)
json.dump(ck, open(CKPT, "w"), default=float)
print(f"\nКривая MW(d): " + " ".join(f"{d}:{MWd[d]:.3f}" if MWd[d] is not None else f"{d}:-" for d in range(1, 7)))
print(f"p(d=1)={p1:.3f} p(d=6)={p6:.3f} | макс. рост {grow:+.3f}")
print(f"P-H1 (монотонность): {'ПОДТВЕРЖДЁН' if ph1 else ('УБИТ' if ph1_kill else 'не установлен')}")
print(f"P-H2 (кромка d_h={dh} в [3,6]): {'ПОДТВЕРЖДЁН' if ph2 else ('УБИТ' if ph2_kill else 'не установлен')}")
print(f"P-H3 (MW_1 >= 0.65): {'подтверждён' if ph3 else 'нет'} (MW_1={MWd[1]:.3f})")
print(f"LOO d_h: {[l['dh'] for l in loo]}")
print(f"[{time.time()-t0:.0f}s]")
