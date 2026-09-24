"""TH pre-freeze calibration (calibration seeds 8100xx) — overshoot sweep at FIXED drive rate.
Checks: do births happen at small overshoot within budget; what S ranges arise. NOT a test run."""
import time
import numpy as np

exec(open("/home/claude/pre006c_run.py").read().split("t0 = time.time()")[0])   # SYS, feat_S, feat_rise_sE, feat_R2, features
EPS_GRID = (0.30, 0.15, 0.07, 0.03)

def par_ramped(p0, thr, eps, t_thr=300.0):
    """Fixed rate: reach thr at t_thr, then keep ramping to p1 = thr + eps*(thr-p0) and HOLD."""
    v = (thr - p0) / t_thr
    p1 = thr + eps * (thr - p0)
    return lambda t: min(p0 + v * t, p1), p1

t0 = time.time()
for name in ("fold", "trans"):
    S_ = SYS[name]; p0, thr = S_["p0"], S_["thr"]
    for eps in EPS_GRID:
        pf, p1 = par_ramped(p0, thr, eps)
        rec = S_["sim"](pf, 810000 + int(eps * 1000) + (0 if name == "fold" else 500), 3)
        out = []
        for r in range(3):
            x = rec[r]
            f = features(x)
            out.append((None if f["S"] is None else round(f["S"], 2), round(f["rise"], 1), round(f["R2"], 1)))
        print(f"{name} ε={eps:.2f} (p1={p1:.3f}): (S, rise, R2) = {out} [{time.time()-t0:.0f}s]", flush=True)
