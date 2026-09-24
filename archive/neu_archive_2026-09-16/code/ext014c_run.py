"""EXT-014c — step certificate v2: decontaminated null, direct permutation p. Per PREREG (frozen 2026-08-31)."""
import json
import numpy as np
import pandas as pd

RNG = np.random.default_rng(20260837)
nile = pd.read_csv("/home/claude/Rdatasets/csv/datasets/Nile.csv")
y = nile["value"].to_numpy(float)
yr0 = int(nile["time"].iloc[0]); n = len(y)

def fit_step(yy):
    best = (None, np.inf, None)
    for k in range(3, n - 3):
        m1, m2 = yy[:k].mean(), yy[k:].mean()
        s = ((yy[:k] - m1) ** 2).sum() + ((yy[k:] - m2) ** 2).sum()
        if s < best[1]: best = (k, s, abs(m2 - m1))
    return best

def fit_kink(yy):
    t = np.arange(n, dtype=float); best = (None, np.inf)
    for k in range(3, n - 3):
        X = np.column_stack([np.ones(n), t, np.maximum(t - k, 0)])
        b, *_ = np.linalg.lstsq(X, yy, rcond=None)
        s = float(((yy - X @ b) ** 2).sum())
        if s < best[1]: best = (k, s)
    return best

def choice(yy):
    ks, ss, _ = fit_step(yy); kk, sk = fit_kink(yy)
    d = (n * np.log(sk / n) + 4 * np.log(n)) - (n * np.log(ss / n) + 3 * np.log(n))
    return ("ступень" if d >= 6 else ("излом" if d <= -6 else "неразличимо")), d

def Kof(yy):
    ks, ss, dm = fit_step(yy)
    return ks, dm / np.sqrt(ss / n)

# ---- decontaminated null: AR(1) on two-segment residuals ----
ks0, sse0, dmu0 = fit_step(y)
r = np.concatenate([y[:ks0] - y[:ks0].mean(), y[ks0:] - y[ks0:].mean()])
phi = float(np.clip(np.corrcoef(r[:-1], r[1:])[0, 1], -0.99, 0.99))
sigr = float(np.sqrt(np.var(r) * (1 - phi ** 2)))
degen = phi >= 0.99
K_data = dmu0 / np.sqrt(sse0 / n)
year = yr0 + ks0
print(f"Нил: k_s={year}, K={K_data:.2f}; φ̂_остатков={phi:.3f} (флаг: {degen}), σ̂={sigr:.1f}")

def ar1(scale):
    x = np.zeros(n); e = RNG.normal(0, scale, n)
    for i in range(1, n): x[i] = phi * x[i - 1] + e[i]
    return x

sur = np.array([Kof(ar1(sigr))[1] for _ in range(1000)])
p_perm = float(np.mean(sur >= K_data))
v_bic, dbic = choice(y)
jack = [yr0 + fit_step(np.delete(y, j))[0] + (1 if j <= ks0 else 0) for j in range(max(ks0 - 3, 0), min(ks0 + 4, n))]
jack_ok = all(abs(jy - year) <= 2 for jy in jack)
pn1 = (1893 <= year <= 1903) and p_perm < 0.05 and v_bic == "ступень"
pn1_kill = not pn1
print(f"P-N1c: позиция {year}, перестановочный p = {p_perm:.4f} (нуль P95={np.percentile(sur,95):.2f} P99={np.percentile(sur,99):.2f}), "
      f"BIC: {v_bic} (Δ={dbic:.1f}), джекнайф: {jack_ok} -> {'ПОДТВЕРЖДЁН' if pn1 else 'УБИТ'}")

# ---- synthetic v2 on fresh seed ----
ok_s = ok_k = 0
for _ in range(20):
    k = RNG.integers(30, 71)
    ys = ar1(sigr); ys[k:] += 2 * r.std() * (1 if RNG.random() < 0.5 else -1)
    ok_s += (choice(ys)[0] == "ступень")
for _ in range(20):
    k = RNG.integers(30, 71)
    yk = ar1(sigr)
    t = np.arange(n, dtype=float)
    yk += (4 * r.std() / (n - k)) * np.maximum(t - k, 0)
    ok_k += (choice(yk)[0] == "излом")
pn2 = ok_s >= 16 and ok_k >= 14
pn2_kill = ok_s <= 10 or ok_k <= 10
print(f"P-N2c: ступени {ok_s}/20 (кромка 16), изломы {ok_k}/20 (кромка 14) -> "
      f"{'ПОДТВЕРЖДЁН' if pn2 else ('УБИТ' if pn2_kill else 'не установлен')}")

json.dump(dict(year=year, K=float(K_data), phi_resid=phi, p_perm=p_perm, bic=v_bic, dbic=float(dbic),
               jack_ok=bool(jack_ok), PN1c=bool(pn1), PN1c_killed=bool(pn1_kill),
               ok_step=ok_s, ok_kink=ok_k, PN2c=bool(pn2), PN2c_killed=bool(pn2_kill), degen_flag=bool(degen)),
          open("/home/claude/ext014c_results.json", "w"), default=float)
print("-> ext014c_results.json")
