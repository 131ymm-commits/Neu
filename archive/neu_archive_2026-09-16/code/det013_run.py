"""DET-013 — Omega-scaling of detection lag. Per PREREG (frozen 2026-08-23).
Full DET-012b protocol re-run at Omega in {2000, 8000}; Omega=500 reused from stored results."""
import json, time
import numpy as np

SEED = 20260837
A = 2.0
DT = 0.005
NTRAJ = 80
B_DEG = [3.0, 3.5, 4.0]
B_WIN = list(np.round(np.linspace(4.6, 6.2, 12), 4))
# rotation leg (DET-012b protocol)
STRIDE_R = 100
NSAMP_R = int(300.0 / (DT * STRIDE_R))    # 600
BURN_R = int(0.05 * NSAMP_R)
# radius leg (DET-012 protocol)
STRIDE_A = 10
NSAMP_A = int(60.0 / (DT * STRIDE_A))     # 1200
DELTA0 = 0.15 * A

def sim_cme(b, ntraj, seed, nsamp, stride, omega, n0x=None, n0y=None):
    rng = np.random.default_rng(seed)
    if n0x is None:
        nx = np.full(ntraj, int(round(A * omega)), dtype=np.int64)
        ny = np.full(ntraj, int(round(b / A * omega)), dtype=np.int64)
    else:
        nx = np.array(n0x, dtype=np.int64); ny = np.array(n0y, dtype=np.int64)
    rx = np.empty((ntraj, nsamp)); ry = np.empty((ntraj, nsamp))
    aW = A * omega
    for i in range(nsamp * stride):
        nxf = nx.astype(float); nyf = ny.astype(float)
        r1 = rng.poisson(aW * DT, ntraj)
        r2 = rng.poisson(nxf * DT)
        r3 = rng.poisson(b * nxf * DT)
        r4 = rng.poisson(nxf * np.maximum(nxf - 1, 0) * nyf / omega**2 * DT)
        nx = np.maximum(nx + r1 - r2 - r3 + r4, 0)
        ny = np.maximum(ny + r3 - r4, 0)
        if (i + 1) % stride == 0:
            k = (i + 1) // stride - 1
            rx[:, k] = nx / omega; ry[:, k] = ny / omega
    return rx, ry

def _runs_const(sym):
    idx = np.flatnonzero(sym)
    if idx.size == 0: return np.empty(0, dtype=int)
    if idx.size == 1: return np.array([1])
    brk = ~((np.diff(idx) == 1) & (sym[idx[1:]] == sym[idx[:-1]]))
    bounds = np.r_[0, np.flatnonzero(brk) + 1, idx.size]
    return np.diff(bounds)

def rot_L(rx, ry, xfp, yfp):
    u = rx - xfp; v = ry - yfp
    phi = np.arctan2(v, u)
    dphi = np.angle(np.exp(1j * np.diff(phi, axis=1)))
    g = np.sign(dphi).astype(np.int8)
    allr = np.concatenate([_runs_const(row) for row in g])
    return float(np.median(allr)), int(allr.size)

def det_cycle_pts(b, n):
    def f(s):
        x, y = s
        return np.array([A - (b + 1) * x + x * x * y, b * x - x * x * y])
    s = np.array([A + DELTA0, b / A]); h = 0.01
    for i in range(6000):
        k1 = f(s); k2 = f(s + h / 2 * k1); k3 = f(s + h / 2 * k2); k4 = f(s + h * k3)
        s = s + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
    pts = []
    for i in range(2000):
        k1 = f(s); k2 = f(s + h / 2 * k1); k3 = f(s + h / 2 * k2); k4 = f(s + h * k3)
        s = s + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        pts.append(s.copy())
    pts = np.array(pts)
    return pts[np.linspace(0, len(pts) - 1, n).astype(int)]

def radius_pair(b, seed, omega):
    xfp, yfp = A, b / A
    if b > 5.0:
        pts = det_cycle_pts(b, NTRAJ)
        n0x = np.round(pts[:, 0] * omega).astype(np.int64)
        n0y = np.round(pts[:, 1] * omega).astype(np.int64)
    else:
        n0x = np.full(NTRAJ, int(round((A + DELTA0) * omega)), dtype=np.int64)
        n0y = np.full(NTRAJ, int(round(b / A * omega)), dtype=np.int64)
    rx, ry = sim_cme(b, NTRAJ, seed, NSAMP_A, STRIDE_A, omega, n0x, n0y)
    R = np.sqrt((rx - xfp) ** 2 + (ry - yfp) ** 2)
    return float(np.median(R[:, 10:110])), float(np.median(R[:, -100:]))

t0 = time.time()
out = {}
for oi, OM in enumerate([2000, 8000]):
    o = {"deg": {}, "win": {}}
    for i, b in enumerate(B_DEG):
        rx, ry = sim_cme(b, NTRAJ, SEED + oi * 500 + i, NSAMP_R, STRIDE_R, OM)
        rx, ry = rx[:, BURN_R:], ry[:, BURN_R:]
        Lr, nr = rot_L(rx, ry, A, b / A)
        Re, Rl = radius_pair(b, SEED + oi * 500 + 100 + i, OM)
        o["deg"][b] = dict(L_rot=Lr, n_rot=nr, R_late=Rl)
        print(f"OM={OM} DEG b={b}: L_rot={Lr:.1f} (n={nr}) R_late={Rl:.4f} [{time.time()-t0:.0f}s]", flush=True)
    LSTAR = max(8.0, 2.5 * max(v["L_rot"] for v in o["deg"].values()))
    RFLOOR = 2.0 * max(v["R_late"] for v in o["deg"].values())
    o["LSTAR"], o["RFLOOR"] = LSTAR, RFLOOR
    o["null_varies"] = bool(o["deg"][4.0]["L_rot"] >= o["deg"][3.0]["L_rot"])
    print(f"OM={OM} FROZEN: L*={LSTAR:.1f} R_floor={RFLOOR:.4f} null_varies={o['null_varies']}", flush=True)
    for i, b in enumerate(B_WIN):
        rx, ry = sim_cme(b, NTRAJ, SEED + oi * 500 + 1000 + i, NSAMP_R, STRIDE_R, OM)
        rx, ry = rx[:, BURN_R:], ry[:, BURN_R:]
        Lr, nr = rot_L(rx, ry, A, b / A)
        Re, Rl = radius_pair(b, SEED + oi * 500 + 3000 + i, OM)
        o1 = bool(Lr >= LSTAR)
        o2 = bool(Rl / Re >= 0.7 and Rl >= RFLOOR)
        o["win"][b] = dict(L_rot=Lr, n_rot=nr, R_early=Re, R_late=Rl, rot1=o1, rot2=o2,
                           det=bool(o1 and o2))
        print(f"OM={OM} WIN b={b}: L_rot={Lr:.1f} (n={nr}) R {Re:.4f}->{Rl:.4f} "
              f"rot={int(o1)}{int(o2)} [{time.time()-t0:.0f}s]", flush=True)
    wins = [o["win"][b]["det"] for b in B_WIN]
    bstar = None
    for j in range(len(B_WIN) - 1):
        if wins[j] and wins[j + 1]:
            bstar = B_WIN[j]; break
    o["bstar"] = bstar
    o["deg_silent"] = bool(all(v["L_rot"] < LSTAR for v in o["deg"].values()))
    o["sub_silent"] = bool(not any(o["win"][b]["det"] for b in B_WIN if b <= 4.8909))
    o["counter_viol"] = [b for b in B_WIN if o["win"][b]["n_rot"] < 100]
    print(f"OM={OM}: b_det = {bstar} (deg_silent={o['deg_silent']} sub_silent={o['sub_silent']} "
          f"counter_viol={o['counter_viol']})", flush=True)
    out[OM] = o

B500 = 5.4727  # from DET-012b
b2, b8 = out[2000]["bstar"], out[8000]["bstar"]
pd1 = (b2 is not None and b8 is not None and b2 <= B500 and b8 <= b2 and b8 < B500)
pd1_kill = (b2 is None or b8 is None or (b2 is not None and b2 > B500) or
            (b2 is not None and b8 is not None and b8 > b2))
pd2 = (b2 in (5.0364, 5.1818) and b8 == 5.0364)
h0 = (b2 == B500 and b8 == B500)
pd3 = (out[2000]["sub_silent"] and out[8000]["sub_silent"] and
       out[2000]["deg_silent"] and out[8000]["deg_silent"])
D12b = json.load(open("/home/claude/det012b_results.json"))
pd4 = all(
    out[OM]["win"][b]["L_rot"] <= 2 * max(D12b["win"][str(b)]["L_rot"], 1) and
    out[OM]["win"][b]["L_rot"] >= 0.5 * D12b["win"][str(b)]["L_rot"]
    for OM in (2000, 8000) for b in B_WIN if b <= 4.8909)
out["verdicts"] = dict(PD1=bool(pd1), PD1_killed=bool(pd1_kill), PD2=bool(pd2),
                       H0_construction=bool(h0), PD3=bool(pd3), PD4=bool(pd4),
                       lag=[0.4727, (b2 or 99) - 5.0, (b8 or 99) - 5.0])
print(f"\nb_det: 500->{B500}, 2000->{b2}, 8000->{b8} (Хопф 5.0)")
print(f"P-D1 (направление): {'ПОДТВЕРЖДЁН' if pd1 else ('УБИТ' if pd1_kill else 'не установлен')}")
print(f"P-D2 (масштаб γ=1): {'ПОДТВЕРЖДЁН' if pd2 else 'нет'} | H0 (пол): {'ЖИВ' if h0 else 'опровергнут' if pd1 else '—'}")
print(f"P-D3 (специфичность): {'ПОДТВЕРЖДЁН' if pd3 else 'УБИТ'}")
print(f"P-D4 (инвариантность подкритики): {'подтверждён' if pd4 else 'не подтверждён'}")

json.dump(out, open("/home/claude/det013_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det013_results.json")
