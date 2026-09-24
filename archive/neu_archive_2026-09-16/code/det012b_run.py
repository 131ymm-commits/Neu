"""DET-012b — transfer part 2: explicit sampling rule w*dt_s ~ 1 rad. Per PREREG.
Rotation leg re-run at stride 100 (dt_s=0.5, T=300); radius leg reused from det012 results."""
import json, time
import numpy as np

SEED = 20260836
A = 2.0
OMEGA = 500
DT = 0.005
STRIDE = 100                  # dt_s = 0.5 ; omega*dt_s = 1.0 rad
T_TOTAL = 300.0
NSAMP = int(T_TOTAL / (DT * STRIDE))     # 600
BURN = int(0.05 * NSAMP)
NTRAJ = 80
B_DEG = [3.0, 3.5, 4.0]
B_WIN = list(np.round(np.linspace(4.6, 6.2, 12), 4))

D12 = json.load(open("/home/claude/det012_results.json"))

def sim_cme(b, ntraj, seed, nsamp, omega=OMEGA, stride=STRIDE):
    rng = np.random.default_rng(seed)
    nx = np.full(ntraj, int(round(A * omega)), dtype=np.int64)
    ny = np.full(ntraj, int(round(b / A * omega)), dtype=np.int64)
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
    return float(np.median(np.concatenate(
        [_runs(np.sign(np.diff(rng.permutation(row))).astype(np.int8), "alt") for row in rx])))

t0 = time.time()
out = {"deg": {}, "win": {}}

for i, b in enumerate(B_DEG):
    rx, ry = sim_cme(b, NTRAJ, SEED + i, NSAMP)
    rx, ry = rx[:, BURN:], ry[:, BURN:]
    Lr, nr = rot_L(rx, ry, A, b / A)
    La, na = alt_L(rx)
    out["deg"][b] = dict(L_rot=Lr, n_rot=nr, L_alt=La)
    print(f"DEG b={b}: L_rot={Lr:.1f} (n={nr}) L_alt={La:.1f} [{time.time()-t0:.0f}s]", flush=True)

maxLr = max(v["L_rot"] for v in out["deg"].values())
maxLa = max(v["L_alt"] for v in out["deg"].values())
LSTAR_ROT = max(8.0, 2.5 * maxLr)
LSTAR_ALT = max(8.0, 2.5 * maxLa)
out["LSTAR_ROT"], out["LSTAR_ALT"] = LSTAR_ROT, LSTAR_ALT
out["null_varies"] = bool(out["deg"][4.0]["L_rot"] >= out["deg"][3.0]["L_rot"])
print(f"FROZEN: L*_rot={LSTAR_ROT:.1f} L*_alt={LSTAR_ALT:.1f} null_varies={out['null_varies']}", flush=True)

RFLOOR = D12["RFLOOR"]
for i, b in enumerate(B_WIN):
    rx, ry = sim_cme(b, NTRAJ, SEED + 1000 + i, NSAMP)
    rx, ry = rx[:, BURN:], ry[:, BURN:]
    Lr, nr = rot_L(rx, ry, A, b / A)
    La, na = alt_L(rx)
    Lsu = alt_surr(rx, SEED + 2000 + i)
    w12 = D12["win"][str(b)] if str(b) in D12["win"] else D12["win"][repr(b)]
    o_rot1 = bool(Lr >= LSTAR_ROT)
    o_rot2 = bool(w12["rot2"])                       # radius leg reused from DET-012
    o_alt = bool(La >= LSTAR_ALT and Lsu > 0 and La / Lsu >= 3.0)
    out["win"][b] = dict(L_rot=Lr, n_rot=nr, L_alt=La, L_alt_surr=Lsu,
                         R_late=w12["R_late"], rot1=o_rot1, rot2=o_rot2, alt=o_alt,
                         det=bool(o_rot1 and o_rot2))
    print(f"WIN b={b}: L_rot={Lr:.1f} (n={nr}) | R_late(012)={w12['R_late']:.3f} | "
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
sub_silent = not any(out["win"][b]["det"] for b in B_WIN if b <= 4.8909)

pc1 = (bstar is not None and 5.0364 <= bstar <= 5.4727 and deg_silent and sub_silent)
pc1p = (bstar is not None and bstar <= 4.8909)
killed = (bstar is None or (bstar is not None and bstar >= 5.6182))
pc2 = not alt_pair
out["verdicts"] = dict(PC1=bool(pc1), PC1prime=bool(pc1p), line_killed=bool(killed),
                       PC2=bool(pc2), deg_silent=bool(deg_silent), sub_silent=bool(sub_silent))
print(f"\nb* = {bstar} (Хопф = 5.0)")
print(f"P-C1 (перенос): {'ПОДТВЕРЖДЁН' if pc1 else 'нет'}")
print(f"P-C1' (квазициклы, ранняя вспышка): {'СРАБОТАЛ -> гнать P-B4' if pc1p else 'нет'}")
print(f"Убийца линии: {'СРАБОТАЛ' if killed else 'нет'}")
print(f"P-C2 (чередование молчит): {'ПОДТВЕРЖДЁН' if pc2 else 'УБИТ'}")

json.dump(out, open("/home/claude/det012b_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det012b_results.json")
