"""DET-011 — NS oscillatory birth certificate v2. Per PREREG (frozen 2026-08-23).
O1' rotation run-length vs degenerate-frozen floor (no shuffle surrogate — DET-010 diagnosis),
O2' radius persistence on deterministic invariant circle, P-Z2 cross to flip AND fold."""
import json, time
import numpy as np

SEED = 20260834
SIGMA = 0.01
T_STEPS = 3000
BURN = int(0.05 * T_STEPS)
NTRAJ = 320
R_DEG = [1.40, 1.55, 1.70]
R_WIN = list(np.round(np.linspace(1.90, 2.22, 12), 4))
N_AMP, T_AMP, DELTA0 = 80, 1000, 0.15

def sim_delayed(r, ntraj, seed, T=T_STEPS, sigma=SIGMA, x0=None, y0=None, burn=True):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0.2, 0.8, ntraj) if x0 is None else np.array(x0, float)
    y = rng.uniform(0.2, 0.8, ntraj) if y0 is None else np.array(y0, float)
    rx = np.empty((ntraj, T)); ry = np.empty((ntraj, T))
    for t in range(T):
        xn = np.clip(r * x * (1 - y) + sigma * rng.standard_normal(ntraj), 0.0, 1.0)
        y = x; x = xn
        rx[:, t] = x; ry[:, t] = y
    if burn: return rx[:, BURN:], ry[:, BURN:]
    return rx, ry

def _runs_const(sym):
    idx = np.flatnonzero(sym)
    if idx.size == 0: return np.empty(0, dtype=int)
    if idx.size == 1: return np.array([1])
    brk = ~((np.diff(idx) == 1) & (sym[idx[1:]] == sym[idx[:-1]]))
    bounds = np.r_[0, np.flatnonzero(brk) + 1, idx.size]
    return np.diff(bounds)

def rot_L(rx, ry, xstar):
    u = rx - xstar; v = ry - xstar
    phi = np.arctan2(v, u)
    dphi = np.angle(np.exp(1j * np.diff(phi, axis=1)))
    g = np.sign(dphi).astype(np.int8)
    allr = np.concatenate([_runs_const(row) for row in g])
    return float(np.median(allr)), int(allr.size)

def det_circle(r):
    """Deterministic attractor points after relaxation (sigma=0)."""
    xs = 1 - 1 / r
    x = np.full(N_AMP, xs + DELTA0); y = np.full(N_AMP, xs)
    # desynchronize: a few noisy steps then long deterministic relaxation
    rng = np.random.default_rng(12345)
    for t in range(50):
        xn = np.clip(r * x * (1 - y) + 0.02 * rng.standard_normal(N_AMP), 0, 1)
        y = x; x = xn
    for t in range(2000):
        xn = np.clip(r * x * (1 - y), 0, 1)
        y = x; x = xn
    return x, y

def radius_pair(r, seed):
    xs = 1 - 1 / r
    if r > 2.0:
        x0, y0 = det_circle(r)
    else:
        x0 = np.full(N_AMP, xs + DELTA0); y0 = np.full(N_AMP, xs)
    rx, ry = sim_delayed(r, N_AMP, seed, T=T_AMP, x0=x0, y0=y0, burn=False)
    R = np.sqrt((rx - xs) ** 2 + (ry - xs) ** 2)
    return float(np.median(R[:, 10:110])), float(np.median(R[:, -100:]))

t0 = time.time()
out = {"deg": {}, "win": {}, "cross": {}}

# ===== Stage A =====
for i, r in enumerate(R_DEG):
    rx, ry = sim_delayed(r, NTRAJ, SEED + i)
    L, nr = rot_L(rx, ry, 1 - 1 / r)
    Re, Rl = radius_pair(r, SEED + 100 + i)
    out["deg"][r] = dict(L=L, n_runs=nr, R_early=Re, R_late=Rl)
    print(f"DEG r={r}: L_rot={L:.1f} (n={nr}) R {Re:.4f}->{Rl:.4f}", flush=True)

maxL = max(v["L"] for v in out["deg"].values())
LSTAR = max(8.0, 2.5 * maxL)
RFLOOR = 2.0 * max(v["R_late"] for v in out["deg"].values())
out["LSTAR"], out["RFLOOR"] = LSTAR, RFLOOR
print(f"FROZEN: L*_rot = {LSTAR:.1f}, R_floor = {RFLOOR:.4f}", flush=True)

# ===== window =====
for i, r in enumerate(R_WIN):
    rx, ry = sim_delayed(r, NTRAJ, SEED + 1000 + i)
    L, nr = rot_L(rx, ry, 1 - 1 / r)
    Re, Rl = radius_pair(r, SEED + 3000 + i)
    o1 = bool(L >= LSTAR)
    o2 = bool(Rl / Re >= 0.7 and Rl >= RFLOOR)
    out["win"][r] = dict(L=L, n_runs=nr, R_early=Re, R_late=Rl,
                         ratio=Rl / Re, O1=o1, O2=o2, det=bool(o1 and o2))
    print(f"WIN r={r}: L_rot={L:.1f} (n={nr}) | R {Re:.4f}->{Rl:.4f} (ratio {Rl/Re:.2f}) | "
          f"O1={int(o1)} O2={int(o2)}", flush=True)

wins = [out["win"][r]["det"] for r in R_WIN]
rstar = None
for j in range(len(R_WIN) - 1):
    if wins[j] and wins[j + 1]:
        rstar = R_WIN[j]; break
out["rstar"] = rstar
deg_silent = all(v["L"] < LSTAR for v in out["deg"].values())
false_below = any(out["win"][r]["det"] for r in R_WIN if float(r) < 2.0)
print(f"\nr*_NS = {rstar} (deg_silent={deg_silent}, false_below_2={false_below})", flush=True)

# ===== P-Z2: cross to flip and fold =====
def sim_flip(r, ntraj, seed, sigma=0.02):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0.2, 0.8, ntraj)
    rec = np.empty((ntraj, T_STEPS))
    for t in range(T_STEPS):
        x = np.clip(r * x * (1 - x) + sigma * rng.standard_normal(ntraj), 0.0, 1.0)
        rec[:, t] = x
    return rec[:, BURN:]

fl = sim_flip(3.16, NTRAJ, SEED + 5000)
Lf, nf = rot_L(fl[:, 1:], fl[:, :-1], 1 - 1 / 3.16)   # embedding (x_t, x_{t-1})
out["cross"]["flip"] = dict(L=Lf, n_runs=nf, fires=bool(Lf >= LSTAR))
print(f"CROSS flip r=3.16: L_rot={Lf:.1f} fires={Lf >= LSTAR}", flush=True)

def sim_schlogl(fr, ntraj, seed):
    k1s, k4s = 5.75, 8.75
    SN1, Ww = 1.37154, 4.00578 - 1.37154
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
    return rec[:, int(0.05 * rec.shape[1]):].astype(float)

sc = sim_schlogl(0.618, 80, SEED + 5001)
med = float(np.median(sc))
Ls, ns_ = rot_L(sc[:, 1:], sc[:, :-1], med)
out["cross"]["fold"] = dict(L=Ls, n_runs=ns_, fires=bool(Ls >= LSTAR))
print(f"CROSS fold fr=0.618: L_rot={Ls:.1f} fires={Ls >= LSTAR}", flush=True)

# ===== verdicts =====
pz1 = (rstar is not None and 2.02 <= rstar <= 2.16 and deg_silent and not false_below)
pz1_kill = (rstar is None or (rstar is not None and rstar > 2.19) or false_below)
pz2 = not (out["cross"]["flip"]["fires"] or out["cross"]["fold"]["fires"])
pz3 = maxL < 8
out["verdicts"] = dict(PZ1=bool(pz1), PZ1_killed=bool(pz1_kill), PZ2=bool(pz2), PZ3=bool(pz3),
                       deg_silent=bool(deg_silent), false_below=bool(false_below))
print(f"\nP-Z1: {'ПОДТВЕРЖДЁН' if pz1 else ('УБИТ' if pz1_kill else 'не установлен')} (r*_NS={rstar})")
print(f"P-Z2: {'ПОДТВЕРЖДЁН' if pz2 else 'УБИТ'} (flip L={Lf:.1f}, fold L={Ls:.1f}, L*={LSTAR:.1f})")
print(f"P-Z3: {'подтверждён' if pz3 else 'не подтверждён'} (max deg L={maxL:.1f})")

json.dump(out, open("/home/claude/det011_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det011_results.json")
