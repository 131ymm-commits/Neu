"""TH calibration 3 (spent seeds 8300xx): relative jump amplitude A_rel vs overshoot, both mechanisms,
park protocol. Pre-freeze arithmetic for the amplitude-scaling certificate."""
import time
import numpy as np
exec(open("/home/claude/pre006c_run.py").read().split("t0 = time.time()")[0])

def par_park(p0, thr, eps, t_thr=300.0):
    v = (thr - p0) / t_thr; p1 = thr + eps * (thr - p0)
    return lambda t: min(p0 + v * t, p1)

def A_rel(x):
    """Relative jump: (median late 10%) / (median of pre-threshold segment), scale-free."""
    e = float(np.median(x[:E_N])); late = float(np.median(x[-len(x) // 10:]))
    return float(late / max(e, 1e-9)), e, late

t0 = time.time()
for name in ("fold", "trans"):
    S_ = SYS[name]; p0, thr = S_["p0"], S_["thr"]
    for eps in (0.30, 0.15, 0.07, 0.03):
        rec = S_["sim"](par_park(p0, thr, eps), 830000 + int(eps * 1000) + (0 if name == "fold" else 500), 4)
        rows = [A_rel(rec[r]) for r in range(4)]
        a = [round(r[0], 2) for r in rows]
        print(f"{name} ε={eps:.2f}: A_rel = {a} (ранняя медиана {rows[0][1]:.2f} → поздняя {rows[0][2]:.2f}) "
              f"[{time.time()-t0:.0f}s]", flush=True)
