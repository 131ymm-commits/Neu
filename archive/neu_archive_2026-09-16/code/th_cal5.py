"""TH calibration 5: DETERMINISTIC mean-field under park-and-hold, both mechanisms.
Question frozen before running: does the S-separation survive parking when noise is absent?"""
import numpy as np
exec(open("/home/claude/pre006c_run.py").read().split("t0 = time.time()")[0])
k1s, k4s = 5.75, 8.75; SN1, Ww = 1.37154, 4.00578 - 1.37154
EPSV, KCAP = 0.1, 5.0

def mf(kind, eps, dt=0.002, T=600.0, t_thr=300.0):
    p0, thr = (0.30, 1.0) if kind == "fold" else (0.50, 1.0)
    v = (thr - p0) / t_thr; p1 = thr + eps * (thr - p0)
    if kind == "fold":
        rts = np.roots([-1.0, k1s, -k4s, SN1 + p0 * Ww]); x = float(np.sort(rts[np.isreal(rts)].real)[0])
    else:
        x = float((-(1 - p0) + np.sqrt((1 - p0) ** 2 + 4 * EPSV / KCAP)) / (2 / KCAP))
    n = int(T / dt); stride = int(REC_DT / dt); rec = np.empty(int(T / REC_DT)); k = 0
    for i in range(n):
        par = min(p0 + v * i * dt, p1)
        if kind == "fold":
            dx = (SN1 + par * Ww) + k1s * x * x - x ** 3 - k4s * x
        else:
            dx = par * x + EPSV - x - x * x / KCAP
        x += dt * dx
        if (i + 1) % stride == 0 and k < len(rec):
            rec[k] = x; k += 1
    return rec

for kind in ("fold", "trans"):
    for eps in (0.30, 0.15, 0.07, 0.03):
        x = mf(kind, eps)
        s = feat_S(x); rise, _ = feat_rise_sE(x)
        e = float(np.median(x[:E_N])); late = float(np.median(x[-60:]))
        print(f"MF-{kind} ε={eps:.2f}: S={None if s is None else round(s,2)} rise={rise:.0f} "
              f"A_rel={late/max(e,1e-9):.2f} ({e:.3f} → {late:.3f})", flush=True)
