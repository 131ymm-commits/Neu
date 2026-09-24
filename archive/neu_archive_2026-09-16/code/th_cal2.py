"""TH calibration 2 (spent seeds 8100xx/8200xx): (a) D-statistic (tail drift) under both protocols,
(b) deterministic MF fold under park-and-hold — third regime probe. Pre-freeze arithmetic."""
import time
import numpy as np
exec(open("/home/claude/pre006c_run.py").read().split("t0 = time.time()")[0])

def par_park(p0, thr, eps, t_thr=300.0):
    v = (thr - p0) / t_thr
    p1 = thr + eps * (thr - p0)
    return lambda t: min(p0 + v * t, p1)

def par_ramp(p0, p1):
    return lambda t: p0 + (p1 - p0) * min(t / T_TOT, 1.0)

def Dstat(x):
    """Tail drift: (median last 10% - median of 10% right after crossing) / jump."""
    n = len(x)
    e = x[:E_N]; medE = float(np.median(e)); late = float(np.median(x[-n // 10:]))
    jump = late - medE
    if abs(jump) < 1e-12: return None
    L80 = medE + 0.8 * jump
    from scipy.ndimage import median_filter
    xm = median_filter(x.astype(float), size=51, mode="nearest")
    hi = np.flatnonzero(xm >= L80) if jump > 0 else np.array([])
    if hi.size == 0: return None
    h0 = int(hi[0])
    seg = x[h0:min(h0 + n // 10, n)]
    if len(seg) < 10: return None
    return float((late - np.median(seg)) / jump)

t0 = time.time()
print("--- (a) D-статистика на калибровочных сидах ---", flush=True)
for name in ("fold", "trans"):
    S_ = SYS[name]; p0, thr, p1o = S_["p0"], S_["thr"], S_["p1"]
    for proto, pf in (("рамп", par_ramp(p0, p1o)), ("парк ε=0.15", par_park(p0, thr, 0.15))):
        rec = S_["sim"](pf, 820000 + (0 if name == "fold" else 500) + (0 if proto == "рамп" else 7), 3)
        ds, ss = [], []
        for r in range(3):
            x = rec[r]; ds.append(Dstat(x)); ss.append(feat_S(x))
        print(f"{name} {proto}: D = {[None if d is None else round(d,3) for d in ds]} | "
              f"S = {[None if s is None else round(s,1) for s in ss]} [{time.time()-t0:.0f}s]", flush=True)

print("--- (b) детерминированный MF-фолд под парковкой (третий режим) ---", flush=True)
k1s, k4s = 5.75, 8.75; SN1, Ww = 1.37154, 4.00578 - 1.37154
def mf_fold(eps, dt=0.002, T=600.0, t_thr=300.0):
    v = (1.0 - 0.30) / t_thr; p1 = 1.0 + eps * (1.0 - 0.30)
    n = int(T / dt); rec = np.empty(int(T / REC_DT)); k = 0
    fr0 = 0.30; k30 = SN1 + fr0 * Ww
    rts = np.roots([-1.0, k1s, -k4s, k30]); rts = np.sort(rts[np.isreal(rts)].real)
    x = float(rts[0])
    stride = int(REC_DT / dt)
    for i in range(n):
        fr = min(0.30 + v * i * dt, p1)
        k3 = SN1 + fr * Ww
        x += dt * (k3 + k1s * x * x - x ** 3 - k4s * x)
        if (i + 1) % stride == 0 and k < len(rec):
            rec[k] = x; k += 1
    return rec
for eps in (0.30, 0.15, 0.07, 0.03, 0.01):
    x = mf_fold(eps)
    s = feat_S(x); rise, _ = feat_rise_sE(x); d = Dstat(x)
    print(f"MF-фолд ε={eps:.2f}: S={None if s is None else round(s,2)} rise={rise:.1f} "
          f"D={None if d is None else round(d,3)} [{time.time()-t0:.0f}s]", flush=True)
