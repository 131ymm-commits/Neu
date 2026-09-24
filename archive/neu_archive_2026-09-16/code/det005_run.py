"""DET-005 — second cascade rung. Per PREREG (deviation: identification at lag 1, plateau {1,3} — mode identity requires odd lags; logged)."""
import json, numpy as np, time

SIGMA = 0.005
T_STEPS, NB, MINVIS, NTRAJ = 3000, 40, 50, 320
BURN = int(0.05 * T_STEPS)
BUDGETS = {"B1": 20, "B2": 80, "B3": 320}
R_DEG = [3.20, 3.30]
R_WIN = list(np.round(np.linspace(3.40, 3.54, 8), 4))
SEED = 20260827

def simulate(r, ntraj, seed, sigma=SIGMA):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0.2, 0.8, ntraj)
    rec = np.empty((ntraj, T_STEPS), dtype=np.int8)
    for t in range(T_STEPS):
        x = np.clip(r * x * (1 - x) + sigma * rng.standard_normal(ntraj), 0.0, 1.0)
        rec[:, t] = np.minimum((x * NB).astype(np.int32), NB - 1)
    return rec[:, BURN:]

def eigs_at(data, lag):
    a0 = data[:, :-lag].astype(np.int32).ravel(); a1 = data[:, lag:].astype(np.int32).ravel()
    C = np.bincount(a0 * NB + a1, minlength=NB * NB).reshape(NB, NB).astype(np.float64)
    keep = C.sum(1) >= MINVIS
    if keep.sum() < 4: return None
    T = C[np.ix_(keep, keep)]
    T = T / T.sum(1, keepdims=True)
    ev = np.linalg.eigvals(T)
    return ev[np.argsort(-np.abs(ev))]

def pi2_R(ev):
    """R2 = t(pi/2-group)/t(next group below), identified at lag 1."""
    if ev is None: return None
    # drop stationary: eigenvalue closest to +1
    i_st = np.argmin(np.abs(ev - 1))
    ev = np.delete(ev, i_st)
    th = np.angle(ev); am = np.abs(ev)
    mask = (np.abs(th) > np.pi / 4) & (np.abs(th) < 3 * np.pi / 4)
    if not mask.any(): return None
    i = int(np.argmax(am * mask))
    a_pi2 = am[i]
    lower = am[(am < a_pi2 * 0.95)]
    if len(lower) == 0: return None
    a_next = float(np.max(lower))
    if not (0 < a_next < 1 and 0 < a_pi2 < 1): return None
    t2 = -1 / np.log(a_pi2); tn = -1 / np.log(a_next)
    return dict(R2=float(t2 / tn), a_pi2=float(a_pi2), th=float(th[i]), t2=float(t2))

def analyze(data):
    e1 = eigs_at(data, 1); e3 = eigs_at(data, 3)
    p1 = pi2_R(e1)
    if p1 is None: return dict(R2=None, plateau=False, th=None)
    # plateau over odd lags {1,3}: implied |lam| per step
    p3 = None
    if e3 is not None:
        i_st = np.argmin(np.abs(e3 - 1)); e3b = np.delete(e3, i_st)
        th3 = np.angle(e3b); am3 = np.abs(e3b)
        m3 = (np.abs(np.abs(th3) - np.pi / 2) < np.pi / 4)
        if m3.any():
            a3 = float(np.max(am3 * m3)) ** (1 / 3)
            p3 = -1 / np.log(a3) if 0 < a3 < 1 else None
    plateau = p3 is not None and abs(p1["t2"] - p3) / np.mean([p1["t2"], p3]) < 0.20
    return dict(R2=p1["R2"], plateau=bool(plateau), th=p1["th"], t2=p1["t2"], a=p1["a_pi2"])

def jack(data, nblocks=40):
    n = data.shape[0]
    bs = max(1, n // nblocks)
    Rs = []
    for b in range(0, n, bs):
        sub = np.concatenate([data[:b], data[b + bs:]], axis=0)
        a = analyze(sub)
        if a["R2"]: Rs.append(a["R2"])
    Rs = np.array(Rs)
    return float(np.percentile(Rs, 16)) if len(Rs) else np.nan

t0 = time.time()
out = {"deg": {}, "win": {}, "surr": [], "expl": {}}
for r in R_DEG:
    rec = simulate(r, NTRAJ, SEED + int(r * 100))
    out["deg"][r] = {bn: analyze(rec[:nt]) for bn, nt in BUDGETS.items()}
    b3 = out["deg"][r]["B3"]
    print(f"DEG r={r}: B3 R2={b3['R2'] and round(b3['R2'],2)} pl={int(b3['plateau'])}", flush=True)
mx = max((out["deg"][r]["B3"]["R2"] or 0) for r in R_DEG)
R2STAR = max(4.0, 2.5 * mx)
out["R2STAR"] = R2STAR
print(f"R2* = {R2STAR:.2f} (max deg B3 = {mx:.2f})", flush=True)

for r in R_WIN:
    rec = simulate(r, NTRAJ, SEED + int(r * 1000))
    e = {}
    for bn, nt in BUDGETS.items():
        a = analyze(rec[:nt])
        if bn == "B3":
            a["j16"] = jack(rec[:nt])
        e[bn] = a
    out["win"][r] = e
    b3 = e["B3"]
    print(f"WIN r={r}: B3 R2={b3['R2'] and round(b3['R2'],2)} pl={int(b3['plateau'])} "
          f"j16={b3.get('j16') and round(b3['j16'],2)} th/pi={b3['th'] and round(b3['th']/np.pi,2)} "
          f"| B1 R2={e['B1']['R2'] and round(e['B1']['R2'],2)}", flush=True)

for r in (3.30, 3.48):
    rec = simulate(r, BUDGETS["B2"], SEED + 777 + int(r * 10))
    rs = np.random.default_rng(777)
    sub = rec.copy()
    for j in range(sub.shape[0]): rs.shuffle(sub[j])
    a = analyze(sub)
    out["surr"].append(dict(r=r, R2=a["R2"], plateau=a["plateau"]))
    print(f"SURR r={r}: R2={a['R2'] and round(a['R2'],2)} pl={int(a['plateau'])}", flush=True)

# exploratory third rung, sigma=0.001
for r in (3.545, 3.552, 3.558):
    rec = simulate(r, 160, SEED + int(r * 10000), sigma=0.001)
    e1 = eigs_at(rec, 1)
    if e1 is not None:
        i_st = np.argmin(np.abs(e1 - 1)); e = np.delete(e1, i_st)
        th = np.angle(e); am = np.abs(e)
        m = (np.abs(np.abs(th) - np.pi / 4) < np.pi / 8) | (np.abs(np.abs(th) - 3 * np.pi / 4) < np.pi / 8)
        top = am[m].max() if m.any() else None
        bulk = am[~m & (np.abs(th) > 0.1)].max() if (~m).any() else None
        out["expl"][r] = dict(pi4_top=top and float(top), other=bulk and float(bulk))
        print(f"EXPL r={r}: pi/4-семейство max|λ|={top and round(float(top),4)} "
              f"прочее max={bulk and round(float(bulk),4)}", flush=True)

json.dump(out, open("/home/claude/det005_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det005_results.json")
