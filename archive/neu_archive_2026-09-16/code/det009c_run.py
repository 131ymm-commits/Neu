"""DET-009c — v3: two-window decay test. Per PREREG. Same sim seeds as 009b."""
import json, numpy as np, time

exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])

SEED9B = 20260832
T_TR = 100.0
STEPS_TR = int(T_TR / DT)
N_HOT = 80

Db = json.load(open("/home/claude/det009b_results.json"))

def mf_states(A, M):
    def run(n0):
        n = n0.copy()
        for _ in range(60000):
            n += 0.01 * (EPS + KAP * (A.T @ hill(n)) - n)
        return n
    return run(np.full(M, EPS)), run(np.full(M, 12.0))

def sim_hot_pts(A, M, seed, init, hi):
    rng = np.random.default_rng(seed)
    n = rng.poisson(np.maximum(np.tile(init, (N_HOT, 1)), 0)).astype(float)
    pdeath = 1 - np.exp(-DT)
    Af = A.astype(float)
    p_half = None
    for s in range(STEPS_TR):
        b = EPS + KAP * (hill(n) @ Af)
        n = np.clip(n + rng.poisson(b * DT) - rng.binomial(n.astype(np.int64), pdeath), 0, NCAP)
        if s == STEPS_TR // 2 - 1:
            p_half = float((n.sum(1) > hi).mean())
    return p_half, float((n.sum(1) > hi).mean())

t0 = time.time()
out = {}
for sg_s, v in Db.items():
    sg = int(sg_s)
    Kc = v["Kc"]
    edges = edges_seq(10, sg)
    entry = {"Kc": Kc, "K": {}}
    for K in (Kc - 1, Kc, Kc + 1):
        A = adj_at(edges, 10, K)
        dark, hot = mf_states(A, 10)
        dl, ht = dark.sum(), hot.sum()
        hi = dl + 0.6 * (ht - dl)
        if ht - dl < 2.0: hi = dl + 6.0
        ph, pT = sim_hot_pts(A, 10, SEED9B + sg * 10 + K + 3, hot if ht - dl >= 2 else np.full(10, EPS), hi)
        e = dict(p_half=ph, p_T=pT, no_decay=bool(pT >= ph - 0.10))
        if K in (Kc, Kc + 1):
            Ad = adj_at(edges, 10, K, dag=True)
            phd, pTd = sim_hot_pts(Ad, 10, SEED9B + sg * 10 + K + 6, hot if ht - dl >= 2 else np.full(10, EPS), hi)
            e["dag_p_half"] = phd; e["dag_p_T"] = pTd
        entry["K"][K] = e
    # v3 verdicts using v2 stored components
    v2K = v["K"]
    def getK(d, K): return d[str(K)] if str(K) in d else d[K]
    det_v3 = all(
        getK(v2K, K)["C1"]["ok"] and getK(v2K, K).get("C2p", False) and entry["K"][K]["no_decay"]
        for K in (Kc, Kc + 1))
    pre2 = getK(v2K, Kc - 1)
    pre_fire_v3 = (pre2["C1"]["ok"] and pre2["p_hot"] >= 0.15 and entry["K"][Kc - 1]["no_decay"])
    entry["detect_v3"] = bool(det_v3)
    entry["pre_fire_v2"] = bool(v["pre_fire"])
    entry["pre_fire_v3"] = bool(pre_fire_v3)
    out[sg_s] = entry
    if v["pre_fire"] or not det_v3:
        e0 = entry["K"][Kc - 1]
        print(f"seed {sg}: Kc={Kc} det_v3={det_v3} preV2={v['pre_fire']}->preV3={pre_fire_v3} "
              f"(pre p:{e0['p_half']:.2f}->{e0['p_T']:.2f})", flush=True)

det = sum(1 for e in out.values() if e["detect_v3"])
pre = sum(1 for e in out.values() if e["pre_fire_v3"])
dag_decay_ok = 0; dag_tot = 0
for e in out.values():
    for K, ek in e["K"].items():
        if "dag_p_half" in ek and ek["dag_p_half"] >= 0.15:
            dag_tot += 1
            if ek["dag_p_T"] < ek["dag_p_half"] - 0.10: dag_decay_ok += 1
print(f"\nP-W1: pre-closure по v3: {pre}/20 (было 2/20 в v2) -> "
      f"{'ПОДТВЕРЖДЁН' if pre == 0 else ('УБИТ' if pre >= 2 else 'не установлен')}")
print(f"P-W2: детекции сохранились {det}/20 -> "
      f"{'ПОДТВЕРЖДЁН' if det >= 19 else ('УБИТ' if det <= 17 else 'не установлен')}")
print(f"P-W3: DAG с p(T/2)>=0.15 затухают между окнами: {dag_decay_ok}/{dag_tot}")
json.dump(out, open("/home/claude/det009c_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det009c_results.json")
