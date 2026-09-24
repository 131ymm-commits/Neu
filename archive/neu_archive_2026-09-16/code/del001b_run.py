"""DEL-001b — softening leg v2: long records, Lorentzian LSQ fit. Per PREREG (frozen 2026-08-26)."""
import json, os, time
import numpy as np
from scipy.signal import welch
from scipy.optimize import curve_fit

BETA, H = 2.336, 4
OMEGA = 200
DT = 0.01
T_TOT, T_BURN, REC_DT = 5400.0, 200.0, 0.1
NS = int((T_TOT - T_BURN) / REC_DT)   # 52000
NPERSEG = 16384
CKPT = "/home/claude/del001b_ckpt.json"
MF_W = {4: 2.2 ** 0.25 * np.sin(np.pi / 4), 5: 2.2 ** 0.2 * np.sin(np.pi / 5), 6: 2.2 ** (1 / 6) * np.sin(np.pi / 6)}
MF_G = {4: 1 - 2.2 ** 0.25 * np.cos(np.pi / 4), 5: 1 - 2.2 ** 0.2 * np.cos(np.pi / 5), 6: 1 - 2.2 ** (1 / 6) * np.cos(np.pi / 6)}

def sim(k, seed, ntraj=5):
    rng = np.random.default_rng(seed)
    n = np.full((ntraj, k), int(round(1.0514 * OMEGA)), dtype=np.int64)
    steps = int(T_TOT / DT); burn = int(T_BURN / DT); stride = int(REC_DT / DT)
    rec = np.empty((ntraj, NS))
    for i in range(steps):
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

def lorentz(w, A, G, w0, C):
    return A * G * G / (G * G + (w - w0) ** 2) + C

def tau_fit(x, k):
    res = x - x.mean()
    f, P = welch(res, fs=1.0 / REC_DT, nperseg=NPERSEG)
    w = 2 * np.pi * f
    wmf = MF_W[k]
    m = (w >= 0.5 * wmf) & (w <= 1.5 * wmf)
    wm, Pm = w[m], P[m]
    dW = w[1] - w[0]
    G0 = abs(MF_G[k])
    try:
        popt, _ = curve_fit(lorentz, wm, Pm,
                            p0=[Pm.max() - Pm.min(), max(G0, dW), wmf, Pm.min()],
                            bounds=([0, dW / 2, 0.5 * wmf, 0], [np.inf, 1.0, 1.5 * wmf, np.inf]),
                            maxfev=20000)
        return float(1.0 / popt[1]), float(popt[2])
    except Exception:
        return None, None

t0 = time.time()
ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
for k in (4, 5, 6):
    key = f"k{k}"
    if key in ck: continue
    recs = sim(k, 970000 + k)
    taus, w0s = [], []
    for r in range(5):
        t_, w0 = tau_fit(recs[r], k)
        taus.append(t_); w0s.append(w0)
    tv = [t_ for t_ in taus if t_ is not None]
    ck[key] = dict(tau=taus, w0=w0s, med=float(np.median(tv)) if tv else None)
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"k={k}: tau={[None if t_ is None else round(t_,1) for t_ in taus]} мед={ck[key]['med']:.1f} "
          f"(MF {1/abs(MF_G[k]):.1f}) w0={[None if v is None else round(v,3) for v in w0s]} "
          f"[{time.time()-t0:.0f}s]", flush=True)

m4, m5, m6 = ck["k4"]["med"], ck["k5"]["med"], ck["k6"]["med"]
pd4b = (None not in (m4, m5, m6)) and (m4 < m5 < m6) and (m6 / m4 >= 3)
pd4b_kill = (None not in (m4, m5, m6)) and not (m4 < m5 < m6)
mf = {4: 7.2, 5: 18.9, 6: 80.6}
within3 = all(ck[f"k{k}"]["med"] is not None and mf[k] / 3 <= ck[f"k{k}"]["med"] <= mf[k] * 3 for k in (4, 5, 6))
ck["verdicts"] = dict(meds=(m4, m5, m6), PD4b=bool(pd4b), PD4b_killed=bool(pd4b_kill), within3=bool(within3))
json.dump(ck, open(CKPT, "w"), default=float)
print(f"\nP-D4b: медианы {m4:.1f} / {m5:.1f} / {m6:.1f} (MF 7.2/18.9/80.6), отношение {m6/m4:.1f} -> "
      f"{'ПОДТВЕРЖДЁН' if pd4b else ('УБИТ' if pd4b_kill else 'не установлен')}")
print(f"P-D4b-2 (фактор 3 от MF): {within3}")
print(f"[{time.time()-t0:.0f}s]")
