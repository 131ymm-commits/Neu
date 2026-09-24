"""DET-009b — v2 certificate on FRESH seeds. Per PREREG."""
import json, numpy as np, time, os

exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])
exec(open("/home/claude/det009_run.py").read().split('CKPT = "/home/claude/det009_ckpt.json"')[0]
     .split('SEED9 = 20260831')[1].replace("SEED9", "_UNUSED", 1) if False else "")

SEED9B = 20260832
T_TR = 100.0
STEPS_TR = int(T_TR / DT)
DREC = REC_EVERY * DT
N_DARK, N_HOT = 160, 80
S_STAR, S_LO, NMIN = 3.0, 2.0, 20

def mf_states(A, M):
    def run(n0):
        n = n0.copy()
        for _ in range(60000):
            n += 0.01 * (EPS + KAP * (A.T @ hill(n)) - n)
        return n
    return run(np.full(M, EPS)), run(np.full(M, 12.0))

def sim_rec(A, M, ntraj, seed, init):
    rng = np.random.default_rng(seed)
    if init is None:
        n = rng.poisson(np.full((ntraj, M), EPS)).astype(float)
    else:
        n = rng.poisson(np.maximum(np.tile(init, (ntraj, 1)), 0)).astype(float)
    rec = np.empty((ntraj, STEPS_TR // REC_EVERY), dtype=np.float32)
    pdeath = 1 - np.exp(-DT)
    Af = A.astype(float)
    for s in range(STEPS_TR):
        b = EPS + KAP * (hill(n) @ Af)
        n = np.clip(n + rng.poisson(b * DT) - rng.binomial(n.astype(np.int64), pdeath), 0, NCAP)
        if (s + 1) % REC_EVERY == 0:
            rec[:, (s + 1) // REC_EVERY - 1] = n.sum(1)
    return rec

def C1_eval(rec, lo, hi):
    waits, crosses = [], []
    for tr in rec:
        ab = np.where(tr > hi)[0]
        if not len(ab): continue
        th = ab[0]
        be = np.where(tr[:th] < lo)[0]
        if not len(be): continue
        waits.append(be[-1] * DREC); crosses.append((th - be[-1]) * DREC)
    w, c = np.array(waits), np.array(crosses)
    n = len(w)
    if n < NMIN: return dict(n=n, S=None, ok=False)
    S = float(np.median(w) / max(np.median(c), DREC))
    ntr = rec.shape[0]; bs = max(1, ntr // 40); js = []
    for b0 in range(0, ntr, bs):
        sub_idx = np.ones(ntr, bool); sub_idx[b0:b0 + bs] = False
        w2, c2 = [], []
        # cheap: recompute on subset
        for tr in rec[sub_idx]:
            ab = np.where(tr > hi)[0]
            if not len(ab): continue
            th = ab[0]
            be = np.where(tr[:th] < lo)[0]
            if not len(be): continue
            w2.append(be[-1]); c2.append(th - be[-1])
        if len(w2) >= 3: js.append(np.median(w2) / max(np.median(c2), 1))
    j16 = float(np.percentile(js, 16)) if js else None
    return dict(n=n, S=S, ok=bool(S >= S_STAR and j16 and j16 >= S_LO), j16=j16)

CKPT = "/home/claude/det009b_ckpt.json"
out = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
t0 = time.time()
good = len(out)
sg = 5101
while good < 20 and sg < 5160:
    if str(sg) in out: sg += 1; continue
    edges = edges_seq(10, sg)
    Kc = k_cycle(edges, 10)
    if Kc is None or Kc > len(edges) - 3: sg += 1; continue
    A0 = adj_at(edges, 10, Kc)
    if not mf_bistable(A0, 10): sg += 1; continue
    entry = {"Kc": Kc, "K": {}}
    for K in (Kc - 1, Kc, Kc + 1):
        A = adj_at(edges, 10, K)
        dark, hot = mf_states(A, 10)
        dl, ht = dark.sum(), hot.sum()
        lo, hi = dl + 0.25 * (ht - dl), dl + 0.6 * (ht - dl)
        if ht - dl < 2.0: lo, hi = dl + 2.0, dl + 6.0
        rec_d = sim_rec(A, 10, N_DARK, SEED9B + sg * 10 + K, None)
        c1 = C1_eval(rec_d, lo, hi)
        rec_h = sim_rec(A, 10, N_HOT, SEED9B + sg * 10 + K + 3, hot if ht - dl >= 2 else None)
        p_hot = float((rec_h[:, -1] > hi).mean())
        e = dict(C1=c1, p_hot=p_hot)
        if K in (Kc, Kc + 1):
            Ad = adj_at(edges, 10, K, dag=True)
            rec_dh = sim_rec(Ad, 10, N_HOT, SEED9B + sg * 10 + K + 6, hot if ht - dl >= 2 else None)
            e["p_dag"] = float((rec_dh[:, -1] > hi).mean())
            e["C2p"] = bool(p_hot >= 0.15 and p_hot - e["p_dag"] >= 0.10)
        entry["K"][K] = e
    okK = {K: entry["K"][K]["C1"]["ok"] and entry["K"][K].get("C2p", False) for K in (Kc, Kc + 1)}
    pre = entry["K"][Kc - 1]
    pre_fire = pre["C1"]["ok"] and pre["p_hot"] >= 0.15
    entry["detect"] = bool(okK[Kc] and okK[Kc + 1])
    entry["pre_fire"] = bool(pre_fire)
    out[str(sg)] = entry
    json.dump(out, open(CKPT, "w"), default=float)
    k0 = entry["K"][Kc]
    print(f"seed {sg}: Kc={Kc} S={k0['C1']['S'] and round(k0['C1']['S'],1)} "
          f"p={k0['p_hot']:.2f} pdag={k0['p_dag']:.2f} detect={entry['detect']} "
          f"pre={pre_fire} [{good+1}/20, {time.time()-t0:.0f}s]", flush=True)
    good += 1; sg += 1

res = list(out.values())
h = sum(1 for e in res if e["detect"])
pre = sum(1 for e in res if e["pre_fire"])
pd_hi = sum(1 for e in res if max(e["K"][k].get("p_dag", 0) for k in e["K"] if "p_dag" in str(e["K"][k]) or "p_dag" in e["K"][k]) >= 0.15 if True)
pd_hi = sum(1 for e in res if max(v.get("p_dag", 0) for v in e["K"].values()) >= 0.15)
Sok = sum(1 for e in res if (e["K"][max(e["K"], key=lambda k: 0 if "p_dag" not in e["K"][k] else 1)]["C1"]["S"] or 0) >= 3)
Sok = sum(1 for e in res if any((v["C1"]["S"] or 0) >= 3 for v in e["K"].values()))
print(f"\nP-V1: детекция у {h}/20 -> {'ПОДТВЕРЖДЁН' if h>=17 else ('УБИТ' if h<=13 else 'не установлен')}")
print(f"P-V2: pre-closure {pre}/20; p_dag>=0.15 у {pd_hi}/20 -> "
      f"{'ПОДТВЕРЖДЁН' if (pre==0 and pd_hi<=1) else ('УБИТ' if (pre>=2 or pd_hi>=2) else 'не установлен')}")
print(f"P-V3: S>=3 у {Sok}/20")
json.dump(out, open("/home/claude/det009b_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det009b_results.json")
