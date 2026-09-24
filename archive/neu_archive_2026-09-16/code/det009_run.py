"""DET-009 — transient birth certificate: spec + validation. Per PREREG."""
import json, numpy as np, time, os

exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])  # model funcs

SEED9 = 20260831
T_TR = 100.0
STEPS_TR = int(T_TR / DT)
DREC = REC_EVERY * DT
N_DARK, N_HOT = 160, 80
S_STAR, S_LO, NMIN, P_STAR = 3.0, 2.0, 20, 0.5

ck = json.load(open("/home/claude/det002r_ckpt.json"))
seeds = {int(k): v for k, v in ck["seeds"].items() if "excluded" not in v}
SILENT = [5006, 5007, 5008, 5012, 5013, 5015, 5018, 5020]
DETECTED = sorted(k for k, v in seeds.items() if v["Kstar"] is not None)

def mf_states(A, M):
    def run(n0):
        n = n0.copy()
        for _ in range(60000):
            n += 0.01 * (EPS + KAP * (A.T @ hill(n)) - n)
        return n
    dark = run(np.full(M, EPS)); hot = run(np.full(M, 12.0))
    return dark, hot

def sim_rec(A, M, ntraj, seed, init):
    rng = np.random.default_rng(seed)
    if init is None:
        n = rng.poisson(np.full((ntraj, M), EPS)).astype(float)
    else:
        n = np.tile(init, (ntraj, 1)).astype(float)
        n = rng.poisson(np.maximum(n, 0)).astype(float)
    rec = np.empty((ntraj, STEPS_TR // REC_EVERY), dtype=np.float32)
    pdeath = 1 - np.exp(-DT)
    Af = A.astype(float)
    for s in range(STEPS_TR):
        b = EPS + KAP * (hill(n) @ Af)
        n = np.clip(n + rng.poisson(b * DT) - rng.binomial(n.astype(np.int64), pdeath), 0, NCAP)
        if (s + 1) % REC_EVERY == 0:
            rec[:, (s + 1) // REC_EVERY - 1] = n.sum(1)
    return rec

def C1_passage(rec, lo, hi):
    waits, crosses = [], []
    for tr in rec:
        above = np.where(tr > hi)[0]
        if len(above) == 0: continue
        t_hi = above[0]
        below = np.where(tr[:t_hi] < lo)[0]
        if len(below) == 0: continue
        t_ll = below[-1]
        waits.append(t_ll * DREC); crosses.append((t_hi - t_ll) * DREC)
    return np.array(waits), np.array(crosses)

def C1_eval(rec, lo, hi):
    w, c = C1_passage(rec, lo, hi)
    n = len(w)
    if n < NMIN: return dict(n=n, S=None, ok=False, j16=None)
    S = float(np.median(w) / max(np.median(c), DREC))
    js = []
    ntr = rec.shape[0]; bs = max(1, ntr // 40)
    for b0 in range(0, ntr, bs):
        sub = np.concatenate([rec[:b0], rec[b0 + bs:]], axis=0)
        w2, c2 = C1_passage(sub, lo, hi)
        if len(w2) >= 3: js.append(np.median(w2) / max(np.median(c2), DREC))
    j16 = float(np.percentile(js, 16)) if js else None
    ok = S >= S_STAR and j16 is not None and j16 >= S_LO
    return dict(n=n, S=S, ok=bool(ok), j16=j16)

def C2_eval(rec, hi):
    p = float((rec[:, -1] > hi).mean())
    return dict(p=p, ok=bool(p >= P_STAR))

CKPT = "/home/claude/det009_ckpt.json"
out = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
t0 = time.time()
for sg in SILENT + DETECTED:
    if str(sg) in out: continue
    edges = edges_seq(10, sg)
    Kc = seeds[sg]["Kc"]
    entry = {"Kc": Kc, "K": {}}
    for K in (Kc - 1, Kc, Kc + 1):
        A = adj_at(edges, 10, K)
        dark, hot = mf_states(A, 10)
        dl, ht = dark.sum(), hot.sum()
        lo, hi = dl + 0.25 * (ht - dl), dl + 0.6 * (ht - dl)
        if ht - dl < 2.0:  # no hot branch in mean-field (pre-closure)
            lo, hi = dl + 2.0, dl + 6.0
        rec_d = sim_rec(A, 10, N_DARK, SEED9 + sg * 10 + K, None)
        c1 = C1_eval(rec_d, lo, hi)
        rec_h = sim_rec(A, 10, N_HOT, SEED9 + sg * 10 + K + 3, hot if ht - dl >= 2 else None)
        c2 = C2_eval(rec_h, hi)
        e = dict(lo=lo, hi=hi, C1=c1, C2=c2)
        if K in (Kc, Kc + 1):
            Ad = adj_at(edges, 10, K, dag=True)
            rec_dh = sim_rec(Ad, 10, N_HOT, SEED9 + sg * 10 + K + 6, hot if ht - dl >= 2 else None)
            e["C2_dag"] = C2_eval(rec_dh, hi)
        entry["K"][K] = e
    # detection: C1&C2 at Kc and Kc+1, C3 = both dag C2 fail
    okK = {K: entry["K"][K]["C1"]["ok"] and entry["K"][K]["C2"]["ok"] for K in (Kc, Kc + 1)}
    c3 = all(not entry["K"][K]["C2_dag"]["ok"] for K in (Kc, Kc + 1))
    pre_fire = entry["K"][Kc - 1]["C1"]["ok"] and entry["K"][Kc - 1]["C2"]["ok"]
    entry["detect"] = bool(okK[Kc] and okK[Kc + 1] and c3)
    entry["c3"] = bool(c3); entry["pre_fire"] = bool(pre_fire)
    out[str(sg)] = entry
    json.dump(out, open(CKPT, "w"), default=float)
    k0 = entry["K"][Kc]
    print(f"seed {sg}{'(S)' if sg in SILENT else ''}: Kc={Kc} "
          f"S={k0['C1']['S'] and round(k0['C1']['S'],1)}(n={k0['C1']['n']}) "
          f"p_hot={k0['C2']['p']:.2f} dagp={k0['C2_dag']['p']:.2f} "
          f"detect={entry['detect']} pre={pre_fire} [{time.time()-t0:.0f}s]", flush=True)

# Schlogl fold validation point (V=30, fr=0.734)
k1s, k4s = 5.75, 8.75
SN1s, Ws = 1.37154, 4.00578 - 1.37154
def schlogl_tr(V, fr, ntraj, seed, init_high):
    k3 = SN1s + fr * Ws
    N = int(np.ceil(V * 4.6)); nv = np.arange(N + 1); xv = nv / V
    Wp = k3 + k1s * xv**2; Wm = k4s * xv + xv**3
    Wp[-1] = 0.0; Wm[0] = 0.0
    LAMs = 275.0
    pu, pd = Wp / LAMs, Wm / LAMs
    rng = np.random.default_rng(seed)
    r = np.roots([-1.0, k1s, -k4s, k3]); r = np.sort(r[np.isreal(r)].real)
    st = np.full(ntraj, int(round(V * (r[2] if init_high else r[0]))), dtype=np.int64)
    steps = int(T_TR * LAMs)
    stride = 16
    rec = np.empty((ntraj, steps // stride), dtype=np.float32)
    for i in range(steps):
        u = rng.random(ntraj)
        up = u < pu[st]; dn = (~up) & (u < pu[st] + pd[st])
        st += up.astype(np.int64) - dn.astype(np.int64)
        if (i + 1) % stride == 0: rec[:, (i + 1) // stride - 1] = st
    return rec / V, r

rec_d, roots = schlogl_tr(30, 0.734, 160, SEED9 + 1, False)
rec_h, _ = schlogl_tr(30, 0.734, 80, SEED9 + 2, True)
lo_s = roots[0] + 0.25 * (roots[2] - roots[0]); hi_s = roots[0] + 0.6 * (roots[2] - roots[0])
DREC_S = 16 / 275.0
def C1s(rec, lo, hi):
    w, c = [], []
    for tr in rec:
        ab = np.where(tr > hi)[0]
        if not len(ab): continue
        th = ab[0]
        be = np.where(tr[:th] < lo)[0]
        if not len(be): continue
        w.append(be[-1] * DREC_S); c.append((th - be[-1]) * DREC_S)
    return np.array(w), np.array(c)
w, c = C1s(rec_d, lo_s, hi_s)
S_s = float(np.median(w) / max(np.median(c), DREC_S)) if len(w) >= NMIN else None
p_s = float((rec_h[:, -1] > hi_s).mean())
print(f"\nSchlogl fold: passages={len(w)} S={S_s and round(S_s,1)} p_hot={p_s:.2f} "
      f"-> C1 {'ok' if (S_s and S_s>=3) else 'fail'}, C2 {'ok' if p_s>=0.5 else 'fail'}")

# verdicts
sil = [out[str(s)] for s in SILENT]
det = [out[str(s)] for s in DETECTED]
h1 = sum(1 for e in sil if e["detect"])
h2 = sum(1 for e in det if e["detect"])
c3all = sum(1 for e in sil + det if e["c3"])
pre = sum(1 for e in sil + det if e["pre_fire"])
Ss = [e["K"][str(e["Kc"])]["C1"]["S"] if str(e["Kc"]) in e["K"] else e["K"][e["Kc"]]["C1"]["S"] for e in sil + det]
print(f"\nP-T1: молчавшие {h1}/8 -> {'ПОДТВЕРЖДЁН' if h1>=6 else ('УБИТ' if h1<=3 else 'не установлен')}")
print(f"P-T2: обычные {h2}/12 -> {'ПОДТВЕРЖДЁН' if h2>=9 else 'не установлен'}")
print(f"P-T3: C3 у {c3all}/20; pre-closure детекций {pre}/20 -> "
      f"{'ПОДТВЕРЖДЁН' if (c3all==20 and pre==0) else ('УБИТ' if (20-c3all)>=2 else 'не установлен')}")
okS = sum(1 for e in sil + det for K in [e["Kc"]] if (e["K"][K]["C1"]["S"] or 0) >= 3 and e["K"][K]["C2"]["ok"])
tot2 = sum(1 for e in sil + det for K in [e["Kc"]] if e["K"][K]["C2"]["ok"])
print(f"P-T5: S>=3 у {okS}/{tot2} сидов с прошедшим C2")
out["_schlogl"] = dict(S=S_s, p=p_s, n=len(w))
json.dump(out, open("/home/claude/det009_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det009_results.json")
