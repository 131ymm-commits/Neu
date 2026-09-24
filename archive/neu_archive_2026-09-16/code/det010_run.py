"""DET-010 — oscillatory birth certificate. Per PREREG (frozen 2026-08-23).
O1 coherence run-length (rel. to shuffle surrogate + degenerate-frozen floor),
O2 amplitude persistence (on-cycle start), P-Y2 Schlogl cross-specificity,
P-Y4 NS rotation version (secondary)."""
import json, time
import numpy as np

SEED = 20260833
SIGMA = 0.02
T_STEPS = 3000
BURN = int(0.05 * T_STEPS)
NTRAJ = 320
R_DEG = [2.60, 2.75, 2.90]
R_WIN = list(np.round(np.linspace(2.96, 3.40, 12), 4))
N_AMP, T_AMP, DELTA0 = 80, 1000, 0.15

# ---------- simulators ----------
def sim_logistic(r, ntraj, seed, T=T_STEPS, sigma=SIGMA, x0=None, burn=True):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0.2, 0.8, ntraj) if x0 is None else np.array(x0, dtype=float)
    rec = np.empty((ntraj, T))
    for t in range(T):
        x = np.clip(r * x * (1 - x) + sigma * rng.standard_normal(ntraj), 0.0, 1.0)
        rec[:, t] = x
    return rec[:, BURN:] if burn else rec

def sim_delayed(r, ntraj, seed, T=T_STEPS, sigma=0.01):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0.2, 0.8, ntraj); y = rng.uniform(0.2, 0.8, ntraj)
    rx = np.empty((ntraj, T)); ry = np.empty((ntraj, T))
    for t in range(T):
        xn = np.clip(r * x * (1 - y) + sigma * rng.standard_normal(ntraj), 0.0, 1.0)
        y = x; x = xn
        rx[:, t] = x; ry[:, t] = y
    return rx[:, BURN:], ry[:, BURN:]

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
    st = np.full(ntraj, int(round(V * rts[0])), dtype=np.int64)  # dark start
    STEPS, STRIDE = 110000, 16
    rec = np.empty((ntraj, STEPS // STRIDE), dtype=np.int16)
    for i in range(STEPS):
        u = rng.random(ntraj)
        up = u < pu[st]; dn = (~up) & (u < pu[st] + pd[st])
        st += up.astype(np.int64) - dn.astype(np.int64)
        if (i + 1) % STRIDE == 0: rec[:, (i + 1) // STRIDE - 1] = st
    return rec[:, int(0.05 * rec.shape[1]):].astype(float)

# ---------- run-length machinery ----------
def _runs(sym, mode):
    """Maximal runs over nonzero symbols of one trajectory.
    mode='alt': strict sign alternation; mode='const': constant sign.
    Zeros break runs and are excluded."""
    idx = np.flatnonzero(sym)
    if idx.size == 0: return np.empty(0, dtype=int)
    if idx.size == 1: return np.array([1])
    adj = np.diff(idx) == 1
    if mode == "alt":
        ok = sym[idx[1:]] == -sym[idx[:-1]]
    else:
        ok = sym[idx[1:]] == sym[idx[:-1]]
    brk = ~(adj & ok)
    bounds = np.r_[0, np.flatnonzero(brk) + 1, idx.size]
    return np.diff(bounds)

def run_stats(data, mode="alt", symbols=False):
    """data: (ntraj, T) values -> pooled runs of sign(diff) (or of given symbols)."""
    allr = []
    for row in data:
        s = row if symbols else np.sign(np.diff(row)).astype(np.int8)
        allr.append(_runs(s, mode))
    allr = np.concatenate(allr)
    return float(np.median(allr)), int(allr.size)

def surrogate_L(data, seed, mode="alt"):
    rng = np.random.default_rng(seed)
    allr = []
    for row in data:
        if mode == "alt":
            sh = rng.permutation(row)                      # shuffle values within traj
            s = np.sign(np.diff(sh)).astype(np.int8)
        else:
            s = rng.permutation(row.astype(np.int8))       # shuffle increment symbols
        allr.append(_runs(s, mode))
    allr = np.concatenate(allr)
    return float(np.median(allr)), int(allr.size)

# ---------- O2 amplitude ----------
def amp_pair(r, seed):
    xstar = 1 - 1 / r
    if r > 3.0:
        s = np.sqrt((r + 1) * (r - 3))
        p = ((r + 1) + s) / (2 * r)
        x0 = np.full(N_AMP, p)                    # start ON deterministic 2-cycle
    else:
        x0 = np.full(N_AMP, xstar + DELTA0)       # fixed point + delta0
    rec = sim_logistic(r, N_AMP, seed, T=T_AMP, x0=x0, burn=False)
    d = np.abs(np.diff(rec, axis=1))
    a_early = float(np.median(d[:, 10:110]))
    a_late = float(np.median(d[:, -100:]))
    return a_early, a_late

t0 = time.time()
out = {"deg": {}, "win": {}, "schlogl": None, "ns": {"deg": {}, "win": {}}}

# ===== Stage A: degenerate points -> freeze floors =====
for i, r in enumerate(R_DEG):
    rec = sim_logistic(r, NTRAJ, SEED + i)
    L, nr = run_stats(rec)
    ae, al = amp_pair(r, SEED + 100 + i)
    out["deg"][r] = dict(L=L, n_runs=nr, A_early=ae, A_late=al)
    print(f"DEG r={r}: L={L:.1f} (n={nr}) A_early={ae:.4f} A_late={al:.4f}", flush=True)

maxL = max(v["L"] for v in out["deg"].values())
LSTAR = max(8.0, 2.5 * maxL)
AFLOOR = 2.0 * max(v["A_late"] for v in out["deg"].values())
out["LSTAR"], out["AFLOOR"] = LSTAR, AFLOOR
print(f"FROZEN: L* = {LSTAR:.1f}, A_floor = {AFLOOR:.4f}", flush=True)

# ===== Stage B: window =====
for i, r in enumerate(R_WIN):
    rec = sim_logistic(r, NTRAJ, SEED + 1000 + i)
    L, nr = run_stats(rec)
    Ls, _ = surrogate_L(rec, SEED + 2000 + i)
    ae, al = amp_pair(r, SEED + 3000 + i)
    o1 = bool(L >= LSTAR and Ls > 0 and L / Ls >= 3.0)
    o2 = bool(al / ae >= 0.7 and al >= AFLOOR)
    out["win"][r] = dict(L=L, L_surr=Ls, n_runs=nr, A_early=ae, A_late=al,
                         ratio=al / ae, O1=o1, O2=o2, det=bool(o1 and o2))
    print(f"WIN r={r}: L={L:.1f} L_surr={Ls:.1f} (x{L/Ls:.1f}) n={nr} | "
          f"A {ae:.4f}->{al:.4f} (ratio {al/ae:.2f}) | O1={int(o1)} O2={int(o2)}", flush=True)

wins = [out["win"][r]["det"] for r in R_WIN]
rstar = None
for j in range(len(R_WIN) - 1):
    if wins[j] and wins[j + 1]:
        rstar = R_WIN[j]; break
out["rstar"] = rstar
deg_silent = all(v["L"] < LSTAR for v in out["deg"].values())
print(f"\nr* = {rstar}", flush=True)

# ===== P-Y2: Schlogl fold transients through O1 =====
srec = sim_schlogl(0.618, 80, SEED + 5000)
sL, snr = run_stats(srec)
sLs, _ = surrogate_L(srec, SEED + 5001)
sratio = sL / sLs if sLs > 0 else np.inf
out["schlogl"] = dict(L=sL, L_surr=sLs, n_runs=snr, ratio=sratio,
                      O1_fires=bool(sL >= LSTAR and sratio >= 3.0))
print(f"SCHLOGL fr=0.618: L={sL:.1f} L_surr={sLs:.1f} ratio={sratio:.2f} "
      f"O1_fires={out['schlogl']['O1_fires']}", flush=True)

# ===== P-Y4: NS rotation version (secondary) =====
NS_DEG = [1.40, 1.55, 1.70]
NS_WIN = list(np.round(np.linspace(1.90, 2.22, 12), 4))

def rot_symbols(rx, ry, r):
    xs = 1 - 1 / r
    u = rx - xs; v = ry - xs
    phi = np.arctan2(v, u)
    dphi = np.angle(np.exp(1j * np.diff(phi, axis=1)))
    return np.sign(dphi).astype(np.int8)

def ns_L(r, seed):
    rx, ry = sim_delayed(r, NTRAJ, seed)
    g = rot_symbols(rx, ry, r)
    allr = [_runs(row, "const") for row in g]
    allr = np.concatenate(allr)
    L = float(np.median(allr))
    rng = np.random.default_rng(seed + 7)
    surr = [_runs(rng.permutation(row), "const") for row in g]
    surr = np.concatenate(surr)
    return L, float(np.median(surr)), int(allr.size)

for i, r in enumerate(NS_DEG):
    L, Ls, nr = ns_L(r, SEED + 6000 + i)
    out["ns"]["deg"][r] = dict(L=L, L_surr=Ls, n_runs=nr)
    print(f"NS DEG r={r}: L={L:.1f} surr={Ls:.1f} (n={nr})", flush=True)
maxLn = max(v["L"] for v in out["ns"]["deg"].values())
LSTAR_NS = max(8.0, 2.5 * maxLn)
out["ns"]["LSTAR"] = LSTAR_NS
print(f"NS FROZEN: L* = {LSTAR_NS:.1f}", flush=True)
for i, r in enumerate(NS_WIN):
    L, Ls, nr = ns_L(r, SEED + 7000 + i)
    o1 = bool(L >= LSTAR_NS and Ls > 0 and L / Ls >= 3.0)
    out["ns"]["win"][r] = dict(L=L, L_surr=Ls, n_runs=nr, O1=o1)
    print(f"NS WIN r={r}: L={L:.1f} surr={Ls:.1f} (x{L/Ls:.1f}) O1={int(o1)}", flush=True)
nsw = [out["ns"]["win"][r]["O1"] for r in NS_WIN]
rstar_ns = None
for j in range(len(NS_WIN) - 1):
    if nsw[j] and nsw[j + 1]:
        rstar_ns = NS_WIN[j]; break
out["ns"]["rstar"] = rstar_ns
print(f"NS r* = {rstar_ns}", flush=True)

# ===== verdicts by the letter =====
py1 = (rstar is not None and 3.02 <= rstar <= 3.15 and deg_silent)
py1_kill = (rstar is None or (rstar is not None and rstar > 3.20))
py2 = not out["schlogl"]["O1_fires"]
py3 = (rstar is not None and abs(rstar - 3.08) <= 0.08)
py4 = (rstar_ns is not None and 1.95 <= rstar_ns <= 2.12)
out["verdicts"] = dict(PY1=bool(py1), PY1_killed=bool(py1_kill), PY2=bool(py2),
                       PY3=bool(py3), PY4=bool(py4), deg_silent=bool(deg_silent))
print(f"\nP-Y1: {'ПОДТВЕРЖДЁН' if py1 else ('УБИТ' if py1_kill else 'не установлен')} (r*={rstar}, deg_silent={deg_silent})")
print(f"P-Y2: {'ПОДТВЕРЖДЁН' if py2 else 'УБИТ'} (Schlogl O1 ratio={sratio:.2f})")
print(f"P-Y3: {'ПОДТВЕРЖДЁН' if py3 else 'не подтверждён'} (|r*-3.08|={abs((rstar or 99)-3.08):.2f})")
print(f"P-Y4: {'подтверждён' if py4 else 'не подтверждён'} (r*_NS={rstar_ns})")

json.dump(out, open("/home/claude/det010_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det010_results.json")
