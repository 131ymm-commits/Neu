"""TH-005 pre-freeze calibration: AC1 of the pre-onset residual as a DYNAMICAL-noise proxy.
Calibration data only: CME calibration seeds (8500xx) + grokking pilot curve (spent seed 101)."""
import numpy as np, time
exec(open("/home/claude/pre006c_run.py").read().split("t0 = time.time()")[0])

def par_park(p0, thr, eps, t_thr=300.0):
    v = (thr - p0) / t_thr; p1 = thr + eps * (thr - p0)
    return lambda t: min(p0 + v * t, p1)
def par_ramp(p0, p1):
    return lambda t: p0 + (p1 - p0) * min(t / T_TOT, 1.0)

def ac1_pre(x, i_on=None, frac=0.4):
    """AC1 of the detrended pre-onset segment (first `frac` of the record by default)."""
    n = len(x); e = np.asarray(x[:int(frac * n)], float)
    t = np.arange(len(e)); res = e - np.polyval(np.polyfit(t, e, 1), t)
    if res.std() == 0: return None
    return float(np.corrcoef(res[:-1], res[1:])[0, 1])

t0 = time.time()
print("--- CME (динамический шум) ---", flush=True)
for kind, off in (("fold", 0), ("trans", 500)):
    S_ = SYS[kind]; p0, thr, p1o = S_["p0"], S_["thr"], S_["p1"]
    for proto, pf in (("рамп", par_ramp(p0, p1o)), ("парк ε=0.15", par_park(p0, thr, 0.15))):
        rec = S_["sim"](pf, 850000 + off + len(proto), 4)
        a = [ac1_pre(rec[r]) for r in range(4)]
        print(f"{kind:5s} {proto:12s}: AC1 = {[None if q is None else round(q,3) for q in a]} [{time.time()-t0:.0f}s]", flush=True)

print("--- гроккинг, ПИЛОТНАЯ кривая (потраченный сид 101) ---", flush=True)
exec(open("/home/claude/grok_cal.py").read().split("t0 = time.time()")[0])
h = run(101, 10.0, 3e-4, 512, 3000, rec_every=2)
te = h[:, 2]
cr = np.flatnonzero(te >= 0.5)
cut = min(3 * int(cr[0]) + 1, len(te))
x = np.interp(np.linspace(0, cut - 1, 200), np.arange(cut), te[:cut])
i_on = int(np.flatnonzero(x >= 0.5)[0])
e = x[:max(i_on - 5, 10)]
t = np.arange(len(e)); res = e - np.polyval(np.polyfit(t, e, 1), t)
sE = 1.4826 * np.median(np.abs(res - np.median(res))) + 1e-12
rise = (float(np.median(x[-20:])) - float(np.median(e))) / sE
print(f"пилот: i_on={i_on}, rise={rise:.1f}, AC1(пре-онсет)={ac1_pre(x, frac=i_on/len(x)):.3f}, "
      f"σ_E={sE:.5f}, уникальных значений в пре-сегменте={len(np.unique(np.round(e,6)))} [{time.time()-t0:.0f}s]")
