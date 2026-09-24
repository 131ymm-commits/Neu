"""DET-012 — transfer of certificate trio to stochastic Brusselator (CME, Hopf).
Per PREREG (frozen 2026-08-23). Frozen recipes from DET-010/011, no per-system tuning."""
import json, time, sys
import numpy as np

SEED = 20260835
A = 2.0
OMEGA = 500
DT = 0.005
STRIDE = 10          # sample dt = 0.05, ~63 samples/period
T_TOTAL = 150.0
NSAMP = int(T_TOTAL / (DT * STRIDE))          # 3000
BURN = int(0.05 * NSAMP)
NTRAJ = 80
B_DEG = [3.0, 3.5, 4.0]
B_WIN = list(np.round(np.linspace(4.6, 6.2, 12), 4))
T_AMP = 60.0
NSAMP_AMP = int(T_AMP / (DT * STRIDE))        # 1200
DELTA0 = 0.15 * A

def sim_cme(b, ntraj, seed, nsamp, n0x=None, n0y=None, omega=OMEGA):
    rng = np.random.default_rng(seed)
    if n0x is None:
        nx = np.full(ntraj, int(round(A * omega)), dtype=np.int64)
        ny = np.full(ntraj, int(round(b / A * omega)), dtype=np.int64)
    else:
        nx = np.array(n0x, dtype=np.int64); ny = np.array(n0y, dtype=np.int64)
    rx = np.empty((ntraj, nsamp)); ry = np.empty((ntraj, nsamp))
    aW = A * omega
    steps = nsamp * STRIDE
    for i in range(steps):
        nxf = nx.astype(float); nyf = ny.astype(float)
        r1 = rng.poisson(aW * DT, ntraj)
        r2 = rng.poisson(nxf * DT)
        r3 = rng.poisson(b * nxf * DT)
        r4 = rng.poisson(nxf * np.maximum(nxf - 1, 0) * nyf / omega**2 * DT)
        nx = np.maximum(nx + r1 - r2 - r3 + r4, 0)
        ny = np.maximum(ny + r3 - r4, 0)
        if (i + 1) % STRIDE == 0:
            k = (i + 1) // STRIDE - 1
            rx[:, k] = nx / omega; ry[:, k] = ny / omega
    return rx, ry

# ---------- run machinery (identical to DET-010/011) ----------
def _runs(sym, mode):
    idx = np.flatnonzero(sym)
    if idx.size == 0: return np.empty(0, dtype=int)
    if idx.size == 1: return np.array([1])
    adj = np.diff(idx) == 1
    ok = (sym[idx[1:]] == -sym[idx[:-1]]) if mode == "alt" else (sym[idx[1:]] == sym[idx[:-1]])
    brk = ~(adj & ok)
    bounds = np.r_[0, np.flatnonzero(brk) + 1, idx.size]
    return np.diff(bounds)

def rot_L(rx, ry, xfp, yfp):
    u = rx - xfp; v = ry - yfp
    phi = np.arctan2(v, u)
    dphi = np.angle(np.exp(1j * np.diff(phi, axis=1)))
    g = np.sign(dphi).astype(np.int8)
    allr = np.concatenate([_runs(row, "const") for row in g])
    return float(np.median(allr)), int(allr.size)

def alt_L(rx):
    allr = np.concatenate([_runs(np.sign(np.diff(row)).astype(np.int8), "alt") for row in rx])
    return float(np.median(allr)), int(allr.size)

def alt_surr(rx, seed):
    rng = np.random.default_rng(seed)
    allr = np.concatenate([_runs(np.sign(np.diff(rng.permutation(row))).astype(np.int8), "alt")
                           for row in rx])
    return float(np.median(allr))

# ---------- deterministic cycle (RK4) ----------
def det_cycle_pts(b, n):
    def f(s):
        x, y = s
        return np.array([A - (b + 1) * x + x * x * y, b * x - x * x * y])
    s = np.array([A + DELTA0, b / A])
    h = 0.01
    for i in range(6000):
        k1 = f(s); k2 = f(s + h / 2 * k1); k3 = f(s + h / 2 * k2); k4 = f(s + h * k3)
        s = s + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
    pts = []
    for i in range(2000):
        k1 = f(s); k2 = f(s + h / 2 * k1); k3 = f(s + h / 2 * k2); k4 = f(s + h * k3)
        s = s + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        pts.append(s.copy())
    pts = np.array(pts)
    idx = np.linspace(0, len(pts) - 1, n).astype(int)
    return pts[idx]

def radius_pair(b, seed):
    xfp, yfp = A, b / A
    if b > 5.0:
        pts = det_cycle_pts(b, NTRAJ)
        n0x = np.round(pts[:, 0] * OMEGA).astype(np.int64)
        n0y = np.round(pts[:, 1] * OMEGA).astype(np.int64)
    else:
        n0x = np.full(NTRAJ, int(round((A + DELTA0) * OMEGA)), dtype=np.int64)
        n0y = np.full(NTRAJ, int(round(b / A * OMEGA)), dtype=np.int64)
    rx, ry = sim_cme(b, NTRAJ, seed, NSAMP_AMP, n0x, n0y)
    R = np.sqrt((rx - xfp) ** 2 + (ry - yfp) ** 2)
    return float(np.median(R[:, 10:110])), float(np.median(R[:, -100:]))

t0 = time.time()
out = {"deg": {}, "win": {}}

# ===== Stage A =====
for i, b in enumerate(B_DEG):
    rx, ry = sim_cme(b, NTRAJ, SEED + i, NSAMP)
    rx, ry = rx[:, BURN:], ry[:, BURN:]
    Lr, nr = rot_L(rx, ry, A, b / A)
    La, na = alt_L(rx)
    Re, Rl = radius_pair(b, SEED + 100 + i)
    out["deg"][b] = dict(L_rot=Lr, n_rot=nr, L_alt=La, n_alt=na, R_early=Re, R_late=Rl)
    print(f"DEG b={b}: L_rot={Lr:.1f} (n={nr}) L_alt={La:.1f} R {Re:.4f}->{Rl:.4f} "
          f"[{time.time()-t0:.0f}s]", flush=True)

maxLr = max(v["L_rot"] for v in out["deg"].values())
maxLa = max(v["L_alt"] for v in out["deg"].values())
LSTAR_ROT = max(8.0, 2.5 * maxLr)
LSTAR_ALT = max(8.0, 2.5 * maxLa)
RFLOOR = 2.0 * max(v["R_late"] for v in out["deg"].values())
out["LSTAR_ROT"], out["LSTAR_ALT"], out["RFLOOR"] = LSTAR_ROT, LSTAR_ALT, RFLOOR
null_varies = out["deg"][4.0]["L_rot"] >= out["deg"][3.0]["L_rot"]
out["null_varies"] = bool(null_varies)
print(f"FROZEN: L*_rot={LSTAR_ROT:.1f} L*_alt={LSTAR_ALT:.1f} R_floor={RFLOOR:.4f} "
      f"null_varies={null_varies}", flush=True)

# ===== window =====
for i, b in enumerate(B_WIN):
    rx, ry = sim_cme(b, NTRAJ, SEED + 1000 + i, NSAMP)
    rx, ry = rx[:, BURN:], ry[:, BURN:]
    Lr, nr = rot_L(rx, ry, A, b / A)
    La, na = alt_L(rx)
    Lsu = alt_surr(rx, SEED + 2000 + i)
    Re, Rl = radius_pair(b, SEED + 3000 + i)
    o_rot1 = bool(Lr >= LSTAR_ROT)
    o_rot2 = bool(Rl / Re >= 0.7 and Rl >= RFLOOR)
    o_alt = bool(La >= LSTAR_ALT and Lsu > 0 and La / Lsu >= 3.0)
    out["win"][b] = dict(L_rot=Lr, n_rot=nr, L_alt=La, L_alt_surr=Lsu, R_early=Re, R_late=Rl,
                         ratio=Rl / Re, rot1=o_rot1, rot2=o_rot2, alt=o_alt,
                         det=bool(o_rot1 and o_rot2))
    print(f"WIN b={b}: L_rot={Lr:.1f} (n={nr}) | R {Re:.4f}->{Rl:.4f} ({Rl/Re:.2f}) | "
          f"L_alt={La:.1f}/{Lsu:.1f} | rot={int(o_rot1)}{int(o_rot2)} alt={int(o_alt)} "
          f"[{time.time()-t0:.0f}s]", flush=True)

wins = [out["win"][b]["det"] for b in B_WIN]
bstar = None
for j in range(len(B_WIN) - 1):
    if wins[j] and wins[j + 1]:
        bstar = B_WIN[j]; break
out["bstar"] = bstar
alt_pair = any(out["win"][B_WIN[j]]["alt"] and out["win"][B_WIN[j + 1]]["alt"]
               for j in range(len(B_WIN) - 1))
deg_silent = all(v["L_rot"] < LSTAR_ROT for v in out["deg"].values())

pb1 = (bstar is not None and 5.0364 <= bstar <= 5.4727 and deg_silent and
       not any(out["win"][b]["det"] for b in B_WIN if b <= 4.8909))
pb1p = (bstar is not None and bstar <= 4.8909)
killed = (bstar is None or (bstar is not None and bstar >= 5.6182))
pb2 = not alt_pair
pb3 = (bstar is not None and bstar <= 5.1818)
out["verdicts"] = dict(PB1=bool(pb1), PB1prime=bool(pb1p), line_killed=bool(killed),
                       PB2=bool(pb2), PB3=bool(pb3), deg_silent=bool(deg_silent))
print(f"\nb* = {bstar} (Хопф = 5.0)")
print(f"P-B1 (перенос): {'ПОДТВЕРЖДЁН' if pb1 else 'нет'}")
print(f"P-B1' (квазициклы): {'СРАБОТАЛ' if pb1p else 'нет'}")
print(f"Убийца линии: {'СРАБОТАЛ' if killed else 'нет'}")
print(f"P-B2 (чередование молчит): {'ПОДТВЕРЖДЁН' if pb2 else 'УБИТ'}")
print(f"P-B3 (тайминг <= 5.1818): {'подтверждён' if pb3 else 'нет'}")

json.dump(out, open("/home/claude/det012_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det012_results.json")
