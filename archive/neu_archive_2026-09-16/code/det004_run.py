"""DET-004 — Neimark-Sacker route. Per PREREG."""
import json, numpy as np, time

SIGMA, NBX = 0.01, 24
NB2 = NBX * NBX
T_STEPS, MINVIS, NTRAJ = 3000, 50, 320
BURN = int(0.05 * T_STEPS)
BUDGETS = {"B1": 20, "B2": 80, "B3": 320}
LAGS = [1, 2, 3, 4, 8]
LAG_MAIN = 4
PLATEAU = [2, 4, 8]
R_DEG = [1.40, 1.55, 1.70]
R_WIN = list(np.round(np.linspace(1.90, 2.22, 12), 4))
SEED = 20260826

def simulate(r, ntraj, seed):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0.2, 0.8, ntraj); y = rng.uniform(0.2, 0.8, ntraj)
    rec = np.empty((ntraj, T_STEPS), dtype=np.int16)
    for t in range(T_STEPS):
        xn = np.clip(r * x * (1 - y) + SIGMA * rng.standard_normal(ntraj), 0.0, 1.0)
        y = x; x = xn
        ix = np.minimum((x * NBX).astype(np.int32), NBX - 1)
        iy = np.minimum((y * NBX).astype(np.int32), NBX - 1)
        rec[:, t] = ix * NBX + iy
    return rec[:, BURN:]

def eigs_at(data, lag, k=10):
    a0 = data[:, :-lag].astype(np.int64).ravel(); a1 = data[:, lag:].astype(np.int64).ravel()
    C = np.bincount(a0 * NB2 + a1, minlength=NB2 * NB2 if NB2 * NB2 < 4e6 else 0)
    C = C.reshape(NB2, NB2).astype(np.float64)
    keep = C.sum(1) >= MINVIS
    if keep.sum() < 5: return None
    T = C[np.ix_(keep, keep)]
    for _ in range(10):
        rs = T.sum(1)
        ok = rs > 0
        if ok.all(): break
        T = T[np.ix_(ok, ok)]
    if T.shape[0] < 5: return None
    T = T / T.sum(1, keepdims=True)
    ev = np.linalg.eigvals(T)
    return ev[np.argsort(-np.abs(ev))][:k]

def top_mode(ev):
    """Drop stationary (closest to +1), return sorted rest + pair info for the top."""
    i_st = int(np.argmin(np.abs(ev - 1)))
    e = np.delete(ev, i_st)
    th = np.angle(e); am = np.abs(e)
    o = np.argsort(-am)
    am, th = am[o], th[o]
    pair = len(am) > 1 and am[1] / am[0] > 0.95 and abs(th[0] + th[1]) < 0.2
    return am, th, bool(pair)

def analyze(data):
    res = {}
    for lag in LAGS:
        ev = eigs_at(data, lag)
        if ev is None: res[lag] = None; continue
        am, th, pair = top_mode(ev)
        t1 = -lag / np.log(am[0]) if 0 < am[0] < 1 else np.nan
        res[lag] = dict(am=float(am[0]), th=float(th[0]), pair=pair, t1=float(t1),
                        am_list=[float(a) for a in am[:6]], th_list=[float(x) for x in th[:6]])
    m = res[LAG_MAIN]
    t1 = m["t1"] if m else np.nan
    ts = [res[l]["t1"] for l in PLATEAU if res[l]]
    plateau = len(ts) == 3 and not np.any(np.isnan(ts)) and (max(ts) - min(ts)) / np.mean(ts) < 0.20
    th1 = res[1]["th"] if res[1] else np.nan
    pair1 = res[1]["pair"] if res[1] else False
    # rotation check l=2,3 vs l=1
    rot_ok = True
    for l in (2, 3):
        if res[l] is None: rot_ok = False; break
        d = np.angle(np.exp(1j * (res[l]["th"] - l * th1)))
        if abs(d) > np.pi / 6: rot_ok = False
    # second harmonic at lag1: any mode with |th| within 2|th1| +- pi/6, below top pair
    harm = False
    if res[1]:
        for a, t in zip(res[1]["am_list"][2:], res[1]["th_list"][2:]):
            if abs(abs(t) - 2 * abs(th1)) < np.pi / 6: harm = True; break
    return dict(t1=float(t1) if t1 == t1 else None, plateau=bool(plateau),
                theta1=float(th1) if th1 == th1 else None, pair=bool(pair1),
                rot_ok=bool(rot_ok), harm=bool(harm))

def jack(data, nblocks=40):
    n = data.shape[0]; bs = max(1, n // nblocks)
    t1s, ths = [], []
    for b in range(0, n, bs):
        sub = np.concatenate([data[:b], data[b + bs:]], axis=0)
        ev4 = eigs_at(sub, LAG_MAIN); ev1 = eigs_at(sub, 1)
        if ev4 is not None:
            am, _, _ = top_mode(ev4)
            if 0 < am[0] < 1: t1s.append(-LAG_MAIN / np.log(am[0]))
        if ev1 is not None:
            _, th, _ = top_mode(ev1)
            ths.append(th[0])
    t1s = np.array(t1s); ths = np.array(ths)
    j16 = float(np.percentile(t1s, 16)) if len(t1s) else np.nan
    Rb = np.abs(np.mean(np.exp(1j * ths))) if len(ths) else np.nan
    csd = float(np.sqrt(max(-2 * np.log(Rb), 0))) if Rb == Rb and Rb > 0 else np.nan
    return j16, csd

t0 = time.time()
out = {"deg": {}, "win": {}, "surr": [], "conv": None, "flip_pts": {}, "fold_pts": {}}
for r in R_DEG:
    rec = simulate(r, NTRAJ, SEED + int(r * 100))
    out["deg"][r] = {bn: analyze(rec[:nt]) for bn, nt in BUDGETS.items()}
    b3 = out["deg"][r]["B3"]
    print(f"DEG r={r}: B3 t1={b3['t1'] and round(b3['t1'],1)} pl={int(b3['plateau'])} pair={int(b3['pair'])}", flush=True)
TSTAR = 5 * max(out["deg"][r]["B3"]["t1"] or 0 for r in R_DEG)
out["TSTAR"] = TSTAR
print(f"T* = {TSTAR:.1f}", flush=True)

for r in R_WIN:
    rec = simulate(r, NTRAJ, SEED + int(r * 1000))
    e = {}
    for bn, nt in BUDGETS.items():
        a = analyze(rec[:nt])
        if bn == "B3":
            a["j16"], a["th_sd"] = jack(rec[:nt])
        e[bn] = a
    out["win"][r] = e
    b3 = e["B3"]
    print(f"WIN r={r}: B3 t1={b3['t1'] and round(b3['t1'],1)} pl={int(b3['plateau'])} "
          f"pair={int(b3['pair'])} th/pi={b3['theta1'] and round(b3['theta1']/np.pi,3)} "
          f"sd={b3['th_sd'] and round(b3['th_sd'],3)} rot={int(b3['rot_ok'])} harm={int(b3['harm'])} "
          f"j16={b3['j16'] and round(b3['j16'],1)}", flush=True)
    if abs(r - 2.045) < 0.02 and out["conv"] is None:
        out["conv"] = dict(r=r, pts=[dict(n=nt, t1=analyze(rec[:nt])["t1"]) for nt in (20, 40, 80, 160, 320)])

for r in (1.40, 2.05, 2.19):
    rec = simulate(r, BUDGETS["B2"], SEED + 777 + int(r * 10))
    rs = np.random.default_rng(777)
    sub = rec.copy()
    for j in range(sub.shape[0]): rs.shuffle(sub[j])
    a = analyze(sub)
    out["surr"].append(dict(r=r, t1=a["t1"], plateau=a["plateau"]))
    print(f"SURR r={r}: t1={a['t1'] and round(a['t1'],2)}", flush=True)

# flip and fold reference points for P-N2/P-N3 (recomputed with the SAME pair-check)
def sim_flip(r, ntraj, seed, sigma=0.02, nb=40):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0.2, 0.8, ntraj)
    rec = np.empty((ntraj, T_STEPS), dtype=np.int16)
    for t in range(T_STEPS):
        x = np.clip(r * x * (1 - x) + sigma * rng.standard_normal(ntraj), 0.0, 1.0)
        rec[:, t] = np.minimum((x * nb).astype(np.int32), nb - 1)
    return rec[:, BURN:], nb

def eig_generic(data, nb, lag):
    a0 = data[:, :-lag].astype(np.int64).ravel(); a1 = data[:, lag:].astype(np.int64).ravel()
    C = np.bincount(a0 * nb + a1, minlength=nb * nb).reshape(nb, nb).astype(np.float64)
    keep = C.sum(1) >= MINVIS
    T = C[np.ix_(keep, keep)]
    for _ in range(10):
        rs = T.sum(1)
        ok = rs > 0
        if ok.all(): break
        T = T[np.ix_(ok, ok)]
    T = T / T.sum(1, keepdims=True)
    ev = np.linalg.eigvals(T)
    return ev[np.argsort(-np.abs(ev))][:10]

for r in (3.08, 3.12, 3.16):
    rec, nb = sim_flip(r, 320, 20260825 + int(r * 1000))
    am, th, pair = top_mode(eig_generic(rec, nb, 1))
    out["flip_pts"][r] = dict(th=float(th[0]), pair=bool(pair))
    print(f"FLIP r={r}: th/pi={th[0]/np.pi:+.3f} pair={int(pair)}", flush=True)

k1s, k4s = 5.75, 8.75
SN1, Ww = 1.37154, 4.00578 - 1.37154
def sim_fold(fr, ntraj, seed):
    k3 = SN1 + fr * Ww
    V, XMAX, LAM = 20, 4.6, 275.0
    N = int(np.ceil(V * XMAX)); nvec = np.arange(N + 1); xv = nvec / V
    Wp = k3 + k1s * xv**2; Wm = k4s * xv + xv**3
    Wp[-1] = 0.0; Wm[0] = 0.0
    pu, pd = Wp / LAM, Wm / LAM
    rng = np.random.default_rng(seed)
    rts = np.roots([-1.0, k1s, -k4s, k3]); rts = np.sort(rts[np.isreal(rts)].real)
    st = np.full(ntraj, int(round(V * rts[0])), dtype=np.int64)
    STEPS, STRIDE = 110000, 16
    rec = np.empty((ntraj, STEPS // STRIDE), dtype=np.int16)
    for i in range(STEPS):
        u = rng.random(ntraj)
        up = u < pu[st]; dn = (~up) & (u < pu[st] + pd[st])
        st += up.astype(np.int64) - dn.astype(np.int64)
        if (i + 1) % STRIDE == 0: rec[:, (i + 1) // STRIDE - 1] = st
    rec = rec[:, int(0.05 * rec.shape[1]):]
    return np.clip(rec // 2, 0, N // 2), N // 2 + 1

for fr in (0.618, 0.734, 0.850):
    rec, nb = sim_fold(fr, 80, 20260826 + int(fr * 1000))
    am, th, pair = top_mode(eig_generic(rec, nb, 1))
    out["fold_pts"][fr] = dict(th=float(th[0]), pair=bool(pair))
    print(f"FOLD fr={fr}: th/pi={th[0]/np.pi:+.3f} pair={int(pair)}", flush=True)

json.dump(out, open("/home/claude/det004_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det004_results.json")
