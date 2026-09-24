"""PRE-001 — precursors of closure. Per PREREG (frozen 2026-08-23).
Chunked: argv gives graph index range; results appended to checkpoint JSON."""
import json, os, sys, time
import numpy as np

exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])

M = 10
SEED = 20260840
SEEDS_G = list(range(5201, 5221))
N_HOT = 40
T_PERS = 100.0
STEPS = int(T_PERS / DT)          # 10000
REC = 100                          # record every 100 steps -> 100 samples
CKPT = "/home/claude/pre001_ckpt.json"

def mf_dark(A, M):
    n = np.full(M, EPS)
    for _ in range(60000):
        n += 0.01 * (EPS + KAP * (A.T @ hill(n)) - n)
    return n

def auc_p(A, M, seed, hi):
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

def reach_pairs(A, M):
    R = A.astype(bool).copy()
    for k in range(M):
        R = R | (R[:, k:k+1] & R[k:k+1, :])
    np.fill_diagonal(R, False)
    return R

def rewire_acyclic(A, M, seed, attempts=200):
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

def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    rx = np.argsort(np.argsort(x)); ry = np.argsort(np.argsort(y))
    if rx.std() == 0 or ry.std() == 0: return 0.0
    return float(np.corrcoef(rx, ry)[0, 1])

i0, i1 = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (0, 20)
ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
t0 = time.time()

for gi in range(i0, i1):
    sg = SEEDS_G[gi]
    if str(sg) in ck: continue
    edges = edges_seq(M, sg)
    Kc = k_cycle(edges, M)
    W = [K for K in range(max(3, Kc - 6), Kc)]
    entry = {"Kc": Kc, "K": {}}
    for K in W:
        A = adj_at(edges, M, K)
        dark = mf_dark(A, M)
        hi = dark.sum() + 6.0
        a_data = auc_p(A, M, SEED + sg * 20 + K, hi)
        At = rewire_acyclic(A, M, SEED + sg * 20 + K + 7)
        darkt = mf_dark(At, M)
        a_twin = auc_p(At, M, SEED + sg * 20 + K + 13, darkt.sum() + 6.0)
        Rp = reach_pairs(A, M)
        Rn = int(Rp.sum())
        rem = [(i, j) for i in range(M) for j in range(M) if i != j and not A[i, j]]
        closing = sum(1 for (i, j) in rem if Rp[j, i])
        entry["K"][K] = dict(auc=a_data, auc_twin=a_twin, R=Rn,
                             rho_reach=closing / len(rem) if rem else 0.0)
    ks = sorted(entry["K"])
    if len(ks) < 2:
        entry.update(sp_data=None, sp_twin=None, sp_R=None, rho_up=None, incomplete=True)
        ck[str(sg)] = entry
        json.dump(ck, open(CKPT, "w"), default=float)
        print(f"g{sg}: Kc={Kc} W={ks} — ОКНО НЕПОЛНОЕ (записано) [{time.time()-t0:.0f}s]", flush=True)
        continue
    aucs = [entry["K"][k]["auc"] for k in ks]
    entry["sp_data"] = spearman(ks, aucs)
    entry["sp_twin"] = spearman(ks, [entry["K"][k]["auc_twin"] for k in ks])
    entry["sp_R"] = spearman([entry["K"][k]["R"] for k in ks], aucs)
    entry["rho_up"] = bool(spearman(ks, [entry["K"][k]["rho_reach"] for k in ks]) > 0)
    ck[str(sg)] = entry
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"g{sg}: Kc={Kc} W={ks} sp={entry['sp_data']:+.2f} twin={entry['sp_twin']:+.2f} "
          f"spR={entry['sp_R']:+.2f} auc(Kc-1)={aucs[-1]:.3f} [{time.time()-t0:.0f}s]", flush=True)

gk = [s for s in ck if s != "verdicts"]
if len(gk) == 20:
    valid = [s for s in gk if ck[s].get("sp_data") is not None]
    n_inc = 20 - len(valid)
    sps = np.array([ck[s]["sp_data"] for s in valid])
    spt = np.array([ck[s]["sp_twin"] for s in valid])
    spr = np.array([ck[s]["sp_R"] for s in valid])
    med, pos = float(np.median(sps)), int((sps > 0).sum())
    pi1 = med >= 0.5 and pos >= 15
    pi1_kill = med <= 0 or pos <= 12
    loo = [float(np.median(np.delete(sps, i))) for i in range(len(sps))]
    loo_ok = all(m >= 0.5 for m in loo)
    medR = float(np.median(spr))
    pi2 = medR >= 0.5
    # P-I3 paired
    n3 = w3 = 0
    for s in gk:
        Kc = ck[s]["Kc"]
        Kk = ck[s]["K"]
        k1, k4 = str(Kc - 1), str(Kc - 4)
        if k1 in Kk and k4 in Kk:
            n3 += 1
            if Kk[k1]["auc"] > Kk[k4]["auc"]: w3 += 1
    pi3 = (w3 >= 15)
    pi3_kill = (w3 <= 12)
    delta = float(np.median(sps - spt))
    pi4 = "a" if delta >= 0.25 else ("b" if abs(delta) < 0.25 else "twin>data")
    rho_up = sum(1 for s in gk if ck[s].get("rho_up"))
    pi5 = rho_up >= 15
    v = dict(n_incomplete=n_inc, median_sp=med, pos=pos, PI1=bool(pi1), PI1_killed=bool(pi1_kill),
             loo_min=min(loo), loo_ok=bool(loo_ok), median_spR=medR, PI2=bool(pi2),
             PI3_w=w3, PI3_n=n3, PI3=bool(pi3), PI3_killed=bool(pi3_kill),
             delta_twin=delta, PI4=pi4, rho_up=rho_up, PI5=bool(pi5),
             median_sp_twin=float(np.median(spt)))
    ck["verdicts"] = v
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"\nP-I1: медиана Спирмена = {med:+.2f}, положительных {pos}/20 -> "
          f"{'ПОДТВЕРЖДЁН' if pi1 else ('УБИТ' if pi1_kill else 'не установлен')} (LOO min {min(loo):+.2f}, ok={loo_ok})")
    print(f"P-I2: медиана Спирмена(R, AUC) = {medR:+.2f} -> {'ПОДТВЕРЖДЁН' if pi2 else ('УБИТ' if medR <= 0 else 'не установлен')}")
    print(f"P-I3: {w3}/{n3} -> {'ПОДТВЕРЖДЁН' if pi3 else ('УБИТ' if pi3_kill else 'не установлен')}")
    print(f"P-I4: Δ(данные-двойник) = {delta:+.2f} -> исход {pi4} (twin медиана {np.median(spt):+.2f})")
    print(f"P-I5: ρ_reach растёт в {rho_up}/20 -> {'подтверждён' if pi5 else 'не подтверждён'}")
print(f"[{time.time()-t0:.0f}s] done {len(gk) if 'gk' in dir() else len(ck)}/20")
