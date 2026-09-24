"""TH-005 pre-freeze calibration: which clock set the wait — dispersion of onset times across replicas.
Calibration seeds 8600xx (spent). CV = std/mean of t_onset within a cell/mechanism."""
import numpy as np, time
exec(open("/home/claude/pre006c_run.py").read().split("t0 = time.time()")[0])
def par_park(p0, thr, eps, t_thr=300.0):
    v = (thr - p0) / t_thr; p1 = thr + eps * (thr - p0)
    return lambda t: min(p0 + v * t, p1)
def par_ramp(p0, p1):
    return lambda t: p0 + (p1 - p0) * min(t / T_TOT, 1.0)

def t_onset(x):
    """First crossing of the mid-level between early and late medians, in record samples."""
    x = np.asarray(x, float); n = len(x)
    e = float(np.median(x[:E_N])); late = float(np.median(x[-n // 10:]))
    if late <= e: return None
    from scipy.ndimage import median_filter
    xm = median_filter(x, size=51, mode="nearest")
    hi = np.flatnonzero(xm >= e + 0.5 * (late - e))
    return None if hi.size == 0 else float(hi[0])

t0 = time.time()
for kind, off in (("fold", 0), ("trans", 500)):
    S_ = SYS[kind]; p0, thr, p1o = S_["p0"], S_["thr"], S_["p1"]
    for proto, pf in (("рамп", par_ramp(p0, p1o)), ("парк ε=0.15", par_park(p0, thr, 0.15)),
                      ("парк ε=0.03", par_park(p0, thr, 0.03))):
        rec = S_["sim"](pf, 860000 + off + len(proto), 8)
        ts = [t_onset(rec[r]) for r in range(8)]
        tv = [q for q in ts if q is not None]
        cv = float(np.std(tv) / np.mean(tv)) if len(tv) >= 3 else None
        print(f"{kind:5s} {proto:12s}: t_onset={[None if q is None else int(q) for q in ts]} -> "
              f"CV={None if cv is None else round(cv,3)} [{time.time()-t0:.0f}s]", flush=True)
