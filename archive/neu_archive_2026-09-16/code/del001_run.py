"""DEL-001 — chain length as birth knob for rotation. Per PREREG (frozen 2026-08-26)."""
import json, os, sys, time
import numpy as np
from scipy.signal import welch

BETA, H = 2.336, 4
OMEGA = 200
DT = 0.01
T_TOT, T_BURN, REC_DT = 1400.0, 200.0, 0.1
NS = int((T_TOT - T_BURN) / REC_DT)          # 12000
WR, SR, LAGR = 2000, 500, 20
CKPT = "/home/claude/del001_ckpt.json"

def mf_run(k, T=3000.0, dt=0.005):
    x = np.full(k, 1.0514)
    x[0] = 1.2  # small kick
    n = int(T / dt)
    tail = []
    for i in range(n):
        d = np.empty(k)
        d[0] = BETA / (1.0 + x[-1] ** H) - x[0]
        d[1:] = x[:-1] - x[1:]
        x += dt * d
        if i > n - int(200 / dt):
            tail.append(x[0])
    tail = np.array(tail)
    return float(tail.max() - tail.min())

def sim(k, seed, ntraj=5, broken=False):
    rng = np.random.default_rng(seed)
    n = np.full((ntraj, k), int(round(1.0514 * OMEGA)), dtype=np.int64)
    steps = int(T_TOT / DT)
    burn = int(T_BURN / DT)
    stride = int(REC_DT / DT)
    rec = np.empty((ntraj, NS))
    ustar = 1.0514 ** H
    bconst = OMEGA * BETA / (1.0 + ustar)
    for i in range(steps):
        if broken:
            b1 = np.full(ntraj, bconst)
        else:
            b1 = OMEGA * BETA / (1.0 + (n[:, -1] / OMEGA) ** H)
        births = np.empty((ntraj, k))
        births[:, 0] = b1
        births[:, 1:] = n[:, :-1]
        n = np.maximum(n + rng.poisson(births * DT) - rng.poisson(n * DT), 0)
        j = i - burn
        if j >= 0 and (j + 1) % stride == 0:
            idx = (j + 1) // stride - 1
            if idx < NS: rec[:, idx] = n[:, 0] / OMEGA
    return rec

def stat_R2(x):
    zs = []
    for s0 in range(0, len(x) - WR + 1, SR):
        seg = x[s0:s0 + WR].astype(float)
        t = np.arange(WR)
        res = seg - np.polyval(np.polyfit(t, seg, 1), t)
        u = res[LAGR:]; v = res[:-LAGR]
        phi = np.arctan2(v, u)
        dphi = np.angle(np.exp(1j * np.diff(phi)))
        sd = dphi.std() + 1e-12
        zs.append(abs(dphi.sum()) / (sd * np.sqrt(dphi.size)))
    return float(max(min(zs[j], zs[j + 1]) for j in range(len(zs) - 1)))

def tau_sp(x):
    res = x - x.mean()
    f, P = welch(res, fs=1.0 / REC_DT, nperseg=4096)
    w = 2 * np.pi * f
    m = w > 0.1
    wm, Pm = w[m], P[m]
    ip = int(np.argmax(Pm))
    half = Pm[ip] / 2.0
    # walk out from the peak to half height, linear interpolation
    def cross(side):
        i = ip
        while 0 < i < len(Pm) - 1:
            j = i + side
            if j < 0 or j >= len(Pm): return None
            if Pm[j] < half:
                # interpolate between j and i
                w1, w2, p1, p2 = wm[i], wm[j], Pm[i], Pm[j]
                return w1 + (w2 - w1) * (p1 - half) / (p1 - p2 + 1e-300)
            i = j
        return None
    lo, hi = cross(-1), cross(+1)
    if lo is None or hi is None: return None
    G = (hi - lo) / 2.0
    return float(1.0 / G) if G > 0 else None

t0 = time.time()
ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}

# ---------- P-D1: MF sanity ----------
if "mf" not in ck:
    a6 = mf_run(6); a7 = mf_run(7)
    ck["mf"] = dict(amp6=a6, amp7=a7, ok=bool(a6 < 0.02 and a7 > 0.05))
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"P-D1 MF: амплитуда хвоста k=6: {a6:.4f} (нужно затухание), k=7: {a7:.4f} (нужен цикл) -> "
          f"{'OK' if ck['mf']['ok'] else 'ПРОВАЛ — стоп'}", flush=True)
if not ck["mf"]["ok"]:
    sys.exit(0)

# ---------- calibration ----------
if "cal" not in ck:
    z3 = [stat_R2(x) for x in sim(3, 940003)]
    z12 = [stat_R2(x) for x in sim(12, 940012)]
    alive = min(z12) > max(z3)
    th = float(np.sqrt(min(z12) * max(z3))) if alive else None
    ck["cal"] = dict(z3=z3, z12=z12, alive=bool(alive), th=th)
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"калибровка: k=3 z={[round(z,1) for z in z3]} | k=12 z={[round(z,1) for z in z12]} | "
          f"alive={alive} th={th} [{time.time()-t0:.0f}s]", flush=True)
if not ck["cal"]["alive"]:
    print("порог мёртв — по предрегистрации записанный исход; стоп")
    sys.exit(0)
TH = ck["cal"]["th"]

# ---------- test scan ----------
for k in range(4, 12):
    key = f"k{k}"
    if key in ck: continue
    recs = sim(k, 950000 + k)
    zs = [stat_R2(x) for x in recs]
    fires = sum(1 for z in zs if z >= TH)
    taus = [tau_sp(x) for x in recs]
    taus_v = [t for t in taus if t is not None]
    ck[key] = dict(z=zs, fires=fires, tau=taus, tau_med=(float(np.median(taus_v)) if taus_v else None))
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"k={k}: z={[round(z,1) for z in zs]} огней {fires}/5 | tau_sp мед={ck[key]['tau_med']} "
          f"[{time.time()-t0:.0f}s]", flush=True)

# ---------- P-D5 broken loop ----------
if "broken" not in ck:
    zs = [stat_R2(x) for x in sim(10, 960010, broken=True)]
    ck["broken"] = dict(z=zs, fires=sum(1 for z in zs if z >= TH))
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"разорванная петля k=10: z={[round(z,1) for z in zs]} огней {ck['broken']['fires']}/5 [{time.time()-t0:.0f}s]", flush=True)

# ---------- verdicts ----------
KS = list(range(4, 12))
fires = {k: ck[f"k{k}"]["fires"] for k in KS}
kdet = None
for k in KS:
    if fires[k] >= 4 and all(fires[q] >= 4 for q in KS if q > k):
        kdet = k; break
mono = True
if kdet is not None:
    for k in KS:
        if k <= kdet - 2 and fires[k] > 1: mono = False
    islands = any(fires[KS[i]] >= 4 and fires[KS[i+1]] <= 1 for i in range(len(KS) - 1))
else:
    islands = False
pd2 = kdet is not None and mono and not islands
pd2_kill = (kdet is None) or islands
pd3 = pd2 and 5 <= kdet <= 9
pd3_kill = pd2 and not (5 <= kdet <= 9)
t4, t5, t6 = (ck["k4"]["tau_med"], ck["k5"]["tau_med"], ck["k6"]["tau_med"])
pd4 = None not in (t4, t5, t6) and t4 < t5 < t6
pd5 = ck["broken"]["fires"] <= 1
pd5_kill = ck["broken"]["fires"] >= 2
# LOO around kdet: recompute kdet dropping one replica at each k near boundary
loo_ok = True
if kdet is not None:
    for kb in (kdet - 1, kdet, kdet + 1):
        if kb not in fires: continue
        zs = ck[f"k{kb}"]["z"]
        for drop in range(5):
            sub = [z for j, z in enumerate(zs) if j != drop]
            f_sub = sum(1 for z in sub if z >= TH)
            # boundary robustness: dropping one replica must not flip fired(>=4/5) into <=1/4 or vice versa
            if fires[kb] >= 4 and f_sub < 3: loo_ok = False
            if fires[kb] <= 1 and f_sub > 2: loo_ok = False
ck["verdicts"] = dict(kdet=kdet, fires=fires, PD2=bool(pd2), PD2_killed=bool(pd2_kill),
                      PD3=bool(pd3), PD3_killed=bool(pd3_kill),
                      tau=(t4, t5, t6), PD4=bool(pd4), PD5=bool(pd5), PD5_killed=bool(pd5_kill),
                      loo_ok=bool(loo_ok))
json.dump(ck, open(CKPT, "w"), default=float)
print(f"\nP-D2 (переключатель): k_det={kdet}, огни={fires} -> "
      f"{'ПОДТВЕРЖДЁН' if pd2 else ('УБИТ' if pd2_kill else 'не установлен')} (LOO={loo_ok})")
print(f"P-D3 (k_det в [5,9] при k*=7): {'ПОДТВЕРЖДЁН' if pd3 else ('УБИТ' if pd3_kill else 'не установлен')}")
print(f"P-D4 (софтенинг): tau_sp мед = {t4} / {t5} / {t6} (MF: 7.2/18.9/80.6) -> "
      f"{'ПОДТВЕРЖДЁН' if pd4 else 'УБИТ'}")
print(f"P-D5 (разорванная петля): {ck['broken']['fires']}/5 -> "
      f"{'ПОДТВЕРЖДЁН' if pd5 else ('УБИТ' if pd5_kill else 'не установлен')}")
print(f"[{time.time()-t0:.0f}s] -> {CKPT}")
