"""DET-007 — binning fix for oscillatory-mode plateau. Per PREREG. Same seeds as DET-005."""
import json, numpy as np, time

SIGMA = 0.005
T_STEPS, MINVIS, NTRAJ = 3000, 50, 320
BURN = int(0.05 * T_STEPS)
R_DEG = [3.20, 3.30]
R_WIN = list(np.round(np.linspace(3.40, 3.54, 8), 4))
SEED = 20260827
NBS = [40, 80, 120]

def simulate_x(r, ntraj, seed):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0.2, 0.8, ntraj)
    rec = np.empty((ntraj, T_STEPS), dtype=np.float32)
    for t in range(T_STEPS):
        x = np.clip(r * x * (1 - x) + SIGMA * rng.standard_normal(ntraj), 0.0, 1.0)
        rec[:, t] = x
    return rec[:, BURN:]

def eigs_at(xdata, nb, lag):
    b = np.minimum((xdata * nb).astype(np.int32), nb - 1)
    a0 = b[:, :-lag].ravel(); a1 = b[:, lag:].ravel()
    C = np.bincount(a0 * nb + a1, minlength=nb * nb).reshape(nb, nb).astype(np.float64)
    keep = C.sum(1) >= MINVIS
    if keep.sum() < 4: return None
    T = C[np.ix_(keep, keep)]
    for _ in range(6):
        ok = T.sum(1) > 0
        if ok.all(): break
        T = T[np.ix_(ok, ok)]
    T = T / T.sum(1, keepdims=True)
    ev = np.linalg.eigvals(T)
    return ev[np.argsort(-np.abs(ev))]

def pi2_t(ev, lag):
    if ev is None: return None, None
    i_st = int(np.argmin(np.abs(ev - 1)))
    e = np.delete(ev, i_st)
    th = np.angle(e); am = np.abs(e)
    # family: at odd lags theta in pi/2-band (mod sign)
    m = (np.abs(np.abs(th) - np.pi / 2) < np.pi / 4)
    if not m.any(): return None, None
    a = float(np.max(am * m))
    if not 0 < a < 1: return None, None
    return -lag / np.log(a), a

def analyze(xdata, nb):
    e1 = eigs_at(xdata, nb, 1); e3 = eigs_at(xdata, nb, 3)
    t1, a1 = pi2_t(e1, 1)
    t3, _ = pi2_t(e3, 3)
    if t1 is None: return dict(R2=None, plateau=False, spread=None)
    spread = abs(t1 - t3) / np.mean([t1, t3]) if t3 else None
    plateau = spread is not None and spread < 0.20
    # R2: vs next group below pi/2 pair (at lag 1)
    i_st = int(np.argmin(np.abs(e1 - 1)))
    e = np.delete(e1, i_st); th = np.angle(e); am = np.abs(e)
    m = (np.abs(np.abs(th) - np.pi / 2) < np.pi / 4)
    a_pi2 = float(np.max(am * m))
    lower = am[am < a_pi2 * 0.95]
    R2 = None
    if len(lower) and 0 < lower.max() < 1:
        R2 = (-1 / np.log(a_pi2)) / (-1 / np.log(float(lower.max())))
    return dict(R2=R2, plateau=bool(plateau), spread=float(spread) if spread else None, t1=t1)

def jack16(xdata, nb, nblocks=40):
    n = xdata.shape[0]; bs = max(1, n // nblocks)
    Rs = []
    for b0 in range(0, n, bs):
        sub = np.concatenate([xdata[:b0], xdata[b0 + bs:]], axis=0)
        a = analyze(sub, nb)
        if a["R2"]: Rs.append(a["R2"])
    return float(np.percentile(Rs, 16)) if Rs else np.nan

t0 = time.time()
out = {str(nb): {"deg": {}, "win": {}} for nb in NBS}
for r in R_DEG + R_WIN:
    xd = simulate_x(r, NTRAJ, SEED + int(r * (100 if r in R_DEG else 1000)))
    for nb in NBS:
        a = analyze(xd, nb)
        if r in R_WIN: a["j16"] = jack16(xd, nb)
        key = "deg" if r in R_DEG else "win"
        out[str(nb)][key][r] = a
    row = " | ".join(f"nb={nb}: R2={out[str(nb)]['deg' if r in R_DEG else 'win'][r]['R2'] and round(out[str(nb)]['deg' if r in R_DEG else 'win'][r]['R2'],2)} "
                     f"spr={out[str(nb)]['deg' if r in R_DEG else 'win'][r]['spread'] and round(out[str(nb)]['deg' if r in R_DEG else 'win'][r]['spread'],2)} "
                     f"pl={int(out[str(nb)]['deg' if r in R_DEG else 'win'][r]['plateau'])}" for nb in NBS)
    print(f"r={r}: {row}", flush=True)

print()
for nb in NBS:
    degmax = max((out[str(nb)]["deg"][r]["R2"] or 0) for r in R_DEG)
    R2STAR = max(4.0, 2.5 * degmax)
    zone = [r for r in R_WIN if r >= 3.44]
    okpl = sum(1 for r in zone if out[str(nb)]["win"][r]["plateau"])
    # full detection: R2>=R2*, plateau, j16>=R2*-1, 2 consecutive
    ok = []
    for r in R_WIN:
        a = out[str(nb)]["win"][r]
        ok.append(a["R2"] is not None and a["R2"] >= R2STAR and a["plateau"]
                  and a.get("j16") == a.get("j16") and a.get("j16", 0) >= R2STAR - 1)
    Kstar = None
    for i in range(len(R_WIN) - 1):
        if ok[i] and ok[i + 1]: Kstar = R_WIN[i]; break
    out[str(nb)]["summary"] = dict(R2STAR=R2STAR, plateau_zone=f"{okpl}/6", Kstar=Kstar)
    print(f"nb={nb}: R2*={R2STAR:.1f} плато в зоне детекции {okpl}/6; K*={Kstar}")
json.dump(out, open("/home/claude/det007_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det007_results.json")
