"""EXT-014b — step certificate + step/kink discriminator. Per PREREG (frozen 2026-08-31).
Order: synthetic validation P-N2 FIRST, then Nile."""
import json
import numpy as np
import pandas as pd

RNG = np.random.default_rng(20260833)

def fit_step(y):
    n = len(y)
    best = (None, np.inf, None)
    for k in range(3, n - 3):
        m1, m2 = y[:k].mean(), y[k:].mean()
        sse = ((y[:k] - m1) ** 2).sum() + ((y[k:] - m2) ** 2).sum()
        if sse < best[1]: best = (k, sse, abs(m2 - m1))
    k, sse, dmu = best
    sig = np.sqrt(sse / n)
    return k, sse, float(dmu / (sig + 1e-12))

def fit_kink(y):
    n = len(y); t = np.arange(n, dtype=float)
    best = (None, np.inf)
    for k in range(3, n - 3):
        X = np.column_stack([np.ones(n), t, np.maximum(t - k, 0)])
        beta, res, *_ = np.linalg.lstsq(X, y, rcond=None)
        sse = float(((y - X @ beta) ** 2).sum())
        if sse < best[1]: best = (k, sse)
    return best

def bic_choice(y):
    n = len(y)
    ks, sse_s, K = fit_step(y)
    kk, sse_k = fit_kink(y)
    bic_s = n * np.log(sse_s / n) + 3 * np.log(n)
    bic_k = n * np.log(sse_k / n) + 4 * np.log(n)
    d = bic_k - bic_s
    verdict = "ступень" if d >= 6 else ("излом" if d <= -6 else "неразличимо")
    return verdict, d, ks, K

def ar1_fit(y):
    z = y - y.mean()
    phi = float(np.clip(np.corrcoef(z[:-1], z[1:])[0, 1], -0.99, 0.99))
    sig = float(np.sqrt(np.var(z) * (1 - phi ** 2)))
    return phi, sig

def ar1_sim(n, phi, sig):
    x = np.zeros(n); e = RNG.normal(0, sig, n)
    for i in range(1, n): x[i] = phi * x[i - 1] + e[i]
    return x

nile = pd.read_csv("/home/claude/Rdatasets/csv/datasets/Nile.csv")
y = nile["value"].to_numpy(float)
yr0 = int(nile["time"].iloc[0])
n = len(y)
phi, sig = ar1_fit(y)
sd = float((y - y.mean()).std())
print(f"Нил: n={n}, {yr0}–{yr0+n-1}; AR(1) φ̂={phi:.3f}, σ̂={sig:.1f} (флаг φ≥0.99: {phi >= 0.99})")

# ---------- P-N2 synthetic validation FIRST ----------
ok_step = ok_kink = 0
for _ in range(20):
    k = RNG.integers(30, 71)
    ys = ar1_sim(n, phi, sig)
    ys[k:] += 2 * sd * (1 if RNG.random() < 0.5 else -1)
    v, d, _, _ = bic_choice(ys)
    ok_step += (v == "ступень")
for _ in range(20):
    k = RNG.integers(30, 71)
    yk = ar1_sim(n, phi, sig)
    t = np.arange(n, dtype=float)
    ramp = np.maximum(t - k, 0)
    slope = 2 * sd / max(ramp.mean() * 2, 1)          # net mean shift comparable to 2*sd
    slope = 2 * sd / (n - k) * 2                       # ramp reaching ~4*sd at the end -> halves differ ~2*sd
    yk += slope * ramp
    v, d, _, _ = bic_choice(yk)
    ok_kink += (v == "излом")
pn2 = ok_step >= 18 and ok_kink >= 18
pn2_kill = ok_step <= 12 or ok_kink <= 12
print(f"P-N2 (синтетика): ступени -> «ступень» {ok_step}/20; изломы -> «излом» {ok_kink}/20 -> "
      f"{'ПОДТВЕРЖДЁН' if pn2 else ('УБИТ' if pn2_kill else 'не установлен')}")

# ---------- Nile ----------
res = dict(phi=phi, sig=sig, ok_step=ok_step, ok_kink=ok_kink, PN2=bool(pn2), PN2_killed=bool(pn2_kill))
if not pn2_kill:
    ks, sse_s, K = fit_step(y)
    year = yr0 + ks
    sur = []
    for _ in range(200):
        _, _, Ks = fit_step(ar1_sim(n, phi, sig))
        sur.append(Ks)
    th = 2.5 * float(np.percentile(sur, 99))
    v, d, _, _ = bic_choice(y)
    jack = [yr0 + fit_step(np.delete(y, j))[0] + (1 if j <= ks else 0) for j in range(max(ks - 3, 0), min(ks + 4, n))]
    jack_ok = all(abs(jy - year) <= 2 for jy in jack)
    pn1 = (1893 <= year <= 1903) and K >= th and v == "ступень"
    pn1_kill = not (1893 <= year <= 1903) or K < th or v == "излом"
    res.update(year=year, K=K, th_sur=th, bic_verdict=v, dbic=d, jack_ok=bool(jack_ok),
               PN1=bool(pn1), PN1_killed=bool(pn1_kill))
    print(f"P-N1 (Нил): позиция {year} (окно [1893,1903]), K_step={K:.2f} против порога {th:.2f}, "
          f"BIC-выбор: {v} (ΔBIC={d:.1f}), джекнайф ±2 года: {jack_ok} -> "
          f"{'ПОДТВЕРЖДЁН' if pn1 else ('УБИТ' if pn1_kill else 'не установлен')}")
json.dump(res, open("/home/claude/ext014b_results.json", "w"), default=float)
print("-> ext014b_results.json")
