"""TH calibration 4 (spent seeds 8400xx): protocol proxy candidates on post-onset tail.
G1 = robust slope of last 40% (per record length) / jump;  G2 = (med last 20% - med middle 20%)/jump."""
import time
import numpy as np
exec(open("/home/claude/pre006c_run.py").read().split("t0 = time.time()")[0])

def par_park(p0, thr, eps, t_thr=300.0):
    v = (thr - p0) / t_thr; p1 = thr + eps * (thr - p0)
    return lambda t: min(p0 + v * t, p1)
def par_ramp(p0, p1):
    return lambda t: p0 + (p1 - p0) * min(t / T_TOT, 1.0)

def G(x):
    n = len(x)
    e = float(np.median(x[:E_N])); late = float(np.median(x[-n // 10:]))
    jump = late - e
    if abs(jump) < 1e-9: return None, None
    tail = x[int(0.6 * n):].astype(float)
    t = np.arange(len(tail), dtype=float)
    sl = np.polyfit(t, tail, 1)[0] * len(tail)          # change across the tail
    g1 = float(sl / jump)
    g2 = float((np.median(x[int(0.8 * n):]) - np.median(x[int(0.6 * n):int(0.8 * n)])) / jump)
    return g1, g2

t0 = time.time()
for name in ("fold", "trans"):
    S_ = SYS[name]; p0, thr, p1o = S_["p0"], S_["thr"], S_["p1"]
    for proto, pf in (("рамп", par_ramp(p0, p1o)), ("парк ε=0.15", par_park(p0, thr, 0.15)),
                      ("парк ε=0.03", par_park(p0, thr, 0.03))):
        rec = S_["sim"](pf, 840000 + (0 if name == "fold" else 500) + len(proto), 5)
        gs = [G(rec[r]) for r in range(5)]
        print(f"{name:5s} {proto:12s}: G1 = {[None if g[0] is None else round(g[0],3) for g in gs]} | "
              f"G2 = {[None if g[1] is None else round(g[1],3) for g in gs]} [{time.time()-t0:.0f}s]", flush=True)
