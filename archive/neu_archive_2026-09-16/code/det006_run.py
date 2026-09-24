"""DET-006 — regime map of gap->lifetime. Per PREREG."""
import json, numpy as np, time

LAGS = [32, 64, 128, 256, 512]
LAG_MAIN = 256
PLATEAU = [128, 256, 512]
MINVIS = 50
NTRAJ = 80
LAM_ = 275.0
STEPS, STRIDE = 110000, 16
SEED = 20260829
k1, k4 = 5.75, 8.75
XMAX = 4.6

grid = json.load(open("/home/claude/det006_grid.json"))

def simulate(V, k3, seed):
    N = int(np.ceil(V * XMAX))
    n = np.arange(N + 1); x = n / V
    Wp = k3 + k1 * x**2; Wm = k4 * x + x**3
    Wp[-1] = 0.0; Wm[0] = 0.0
    pu, pd = Wp / LAM_, Wm / LAM_
    rng = np.random.default_rng(seed)
    r = np.roots([-1.0, k1, -k4, k3]); r = np.sort(r[np.isreal(r)].real)
    st = np.full(NTRAJ, int(round(V * r[0])), dtype=np.int64)
    rec = np.empty((NTRAJ, STEPS // STRIDE), dtype=np.int16)
    for i in range(STEPS):
        u = rng.random(NTRAJ)
        up = u < pu[st]; dn = (~up) & (u < pu[st] + pd[st])
        st += up.astype(np.int64) - dn.astype(np.int64)
        if (i + 1) % STRIDE == 0: rec[:, (i + 1) // STRIDE - 1] = st
    return rec[:, int(0.05 * rec.shape[1]):], N

def t2_est(data, N):
    b = np.clip(data.astype(np.int32) // 2, 0, N // 2)
    nb = N // 2 + 1
    res = {}
    for lag in LAGS:
        a0 = b[:, :-lag].ravel(); a1 = b[:, lag:].ravel()
        C = np.bincount(a0 * nb + a1, minlength=nb * nb).reshape(nb, nb).astype(np.float64)
        C = C + C.T
        keep = C.sum(1) >= MINVIS
        if keep.sum() < 3: res[lag] = np.nan; continue
        Ck = C[np.ix_(keep, keep)]
        s = Ck.sum(1)
        A2 = Ck / np.sqrt(np.outer(s, s))
        evv = np.sort(np.linalg.eigvalsh((A2 + A2.T) / 2))[::-1]
        tau = lag * STRIDE / LAM_
        res[lag] = -tau / np.log(evv[1]) if 0 < evv[1] < 1 else np.nan
    t2 = res[LAG_MAIN]
    ts = [res[l] for l in PLATEAU]
    pl = (not np.any(np.isnan(ts))) and (max(ts) - min(ts)) / np.mean(ts) < 0.20
    return t2, pl

t0 = time.time()
out = []
for p in grid:
    rec, N = simulate(p["V"], p["k3"], SEED + p["V"] * 100 + int(p["fr"] * 100))
    t2, pl = t2_est(rec, N)
    q = dict(p); q["t2_emp"] = float(t2) if t2 == t2 else None; q["plateau"] = bool(pl)
    out.append(q)
    print(f"V={p['V']} fr={p['fr']:.2f} [{p['regime']:>3}]: t2_emp={t2:7.1f} pl={int(pl)} "
          f"| tex={p['tex']:6.1f} Thl={p['Thl']:6.1f}", flush=True)

from scipy.stats import spearmanr
val = [q for q in out if q["t2_emp"]]
rho, pv = spearmanr([q["t2_emp"] for q in val], [q["tex"] for q in val])
err = [abs(np.log(q["t2_emp"] / q["tex"])) for q in val]
med_err = float(np.exp(np.median(err)))
print(f"\nP-G1: n={len(val)} rho={rho:.3f} медианная ошибка x{med_err:.2f} "
      f"-> {'ПОДТВЕРЖДЁН' if (rho>=0.9 and med_err<=1.5) else ('УБИТ' if (rho<0.7 or med_err>2.5) else 'не установлен')}")
inr = [q for q in val if q["regime"] == "in"]
outr = [q for q in val if q["regime"] == "out"]
in_err = float(np.exp(np.median([abs(np.log(q["t2_emp"] / q["Thl"])) for q in inr])))
out_low = sum(1 for q in outr if q["t2_emp"] / q["Thl"] < 2/3)
out_ok15 = sum(1 for q in outr if abs(np.log(q["t2_emp"] / q["Thl"])) <= np.log(1.5))
print(f"P-G2: in-режим ({len(inr)} тчк) медианная ошибка t2 vs Thl x{in_err:.2f}; "
      f"out-режим: t2/Thl<2/3 в {out_low}/{len(outr)} (в пределах x1.5: {out_ok15})")
p_g2 = (in_err <= 1.5 and out_low >= 6)
kill_g2 = (in_err > 2.5 or out_ok15 >= 4)
print(f"   -> {'ПОДТВЕРЖДЁН' if p_g2 else ('УБИТ' if kill_g2 else 'не установлен')}")
noplat = [q for q in out if not q["plateau"]]
print(f"P-G3: точек без плато {len(noplat)}; их tex: {sorted(round(q['tex']) for q in noplat)} (T/4 = 100)")
json.dump(dict(points=out, rho=float(rho), med_err=med_err, in_err=in_err,
               out_low=out_low, out_n=len(outr)),
          open("/home/claude/det006_results.json", "w"))
print(f"[{time.time()-t0:.0f}s] -> det006_results.json")
