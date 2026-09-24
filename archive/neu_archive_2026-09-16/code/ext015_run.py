"""EXT-015 — step certificate v2 on the TCPD corpus. Per PREREG (frozen 2026-09-01)."""
import json, os, time
import numpy as np

RNG = np.random.default_rng(20260903)
BASE = "/home/claude/TCPD/datasets"
ANN = json.load(open("/home/claude/TCPD/annotations.json"))
SERIES = ["bank", "brent_spot", "businv", "children_per_woman", "co2_canada", "construction",
          "gdp_argentina", "gdp_iran", "gdp_japan", "global_co2", "homeruns", "jfk_passengers",
          "lga_passengers", "nile", "ozone", "quality_control_1", "quality_control_2",
          "quality_control_3", "quality_control_4", "quality_control_5", "seatbelts",
          "shanghai_license", "uk_coal_employ", "unemployment_nl", "us_population", "usd_isk", "well_log"]
CK = "/home/claude/ext015_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()

def step_scan(y):
    """Vectorized best two-mean split: returns k*, SSE*, K = |dmu|/sigma_resid."""
    n = len(y)
    c1 = np.cumsum(y); c2 = np.cumsum(y * y)
    k = np.arange(3, n - 2)                       # split index: left = y[:k]
    s1l = c1[k - 1]; s2l = c2[k - 1]
    s1r = c1[-1] - s1l; s2r = c2[-1] - s2l
    nl = k; nr = n - k
    sse = (s2l - s1l ** 2 / nl) + (s2r - s1r ** 2 / nr)
    j = int(np.argmin(sse))
    ks = int(k[j])
    dmu = abs(s1r[j] / nr[j] - s1l[j] / nl[j])
    K = float(dmu / np.sqrt(sse[j] / n + 1e-300))
    return ks, float(sse[j]), K

def kink_sse(y):
    n = len(y); t = np.arange(n, dtype=float)
    best = np.inf
    for k in range(3, n - 3):
        X = np.column_stack([np.ones(n), t, np.maximum(t - k, 0)])
        b, *_ = np.linalg.lstsq(X, y, rcond=None)
        s = float(((y - X @ b) ** 2).sum())
        if s < best: best = s
    return best

rows = []
for name in SERIES:
    if name in ck: rows.append(ck[name]); continue
    obj = json.load(open(f"{BASE}/{name}/{name}.json"))
    raw = obj["series"][0]["raw"]
    y = np.array([v if v is not None else np.nan for v in raw], float)
    if np.isnan(y).any():
        ix = np.arange(len(y)); y = np.interp(ix, ix[~np.isnan(y)], y[~np.isnan(y)])
    n = len(y)
    ks, sse_s, K = step_scan(y)
    r = np.concatenate([y[:ks] - y[:ks].mean(), y[ks:] - y[ks:].mean()])
    phi = float(np.clip(np.corrcoef(r[:-1], r[1:])[0, 1], -0.999, 0.999))
    if phi >= 0.99:
        row = dict(name=name, n=n, excluded="phi>=0.99", phi=phi)
        ck[name] = row; rows.append(row); json.dump(ck, open(CK, "w"), default=float)
        print(f"{name}: ИСКЛЮЧЁН (φ̂={phi:.3f})", flush=True); continue
    sigr = float(np.sqrt(max(np.var(r) * (1 - phi ** 2), 1e-300)))
    # surrogate max-K null (vectorized AR(1))
    e = RNG.normal(0, sigr, (1000, n))
    sur = np.empty(1000)
    x = np.zeros((1000, n))
    for i in range(1, n): x[:, i] = phi * x[:, i - 1] + e[:, i]
    for s in range(1000): _, _, sur[s] = step_scan(x[s])
    p = float(np.mean(sur >= K))
    # BIC step vs kink
    sse_k = kink_sse(y)
    dbic = (n * np.log(sse_k / n) + 4 * np.log(n)) - (n * np.log(sse_s / n) + 3 * np.log(n))
    bic = "ступень" if dbic >= 6 else ("излом" if dbic <= -6 else "неразличимо")
    # annotations: union of annotators
    union = sorted({a for v in ANN.get(name, {}).values() for a in v})
    tol = max(5, int(0.02 * n))
    hit = bool(union) and any(abs(ks - a) <= tol for a in union)
    fired = p < 0.05
    dmu_sign = float(np.sign(y[ks:].mean() - y[:ks].mean()))
    row = dict(name=name, n=n, k=ks, K=K, p=p, phi=phi, bic=bic, dbic=float(dbic),
               ann=union, tol=tol, fired=bool(fired), hit=bool(hit), sign=dmu_sign)
    ck[name] = row; rows.append(row); json.dump(ck, open(CK, "w"), default=float)
    print(f"{name}: n={n} k*={ks} K={K:.2f} p={p:.3f} BIC:{bic} | аннот.{union[:6]}{'...' if len(union)>6 else ''} "
          f"tol={tol} -> {'ОГОНЬ' if fired else 'тихо'}{' ПОПАЛ' if fired and hit else (' мимо' if fired and union else '')} "
          f"знак {'+' if dmu_sign>0 else '-'} [{time.time()-t0:.0f}s]", flush=True)

val = [r for r in rows if "excluded" not in r]
fired_ann = [r for r in val if r["fired"] and r["ann"]]
hits = sum(1 for r in fired_ann if r["hit"])
hr = hits / len(fired_ann) if fired_ann else None
nile = ck.get("nile", {})
pb2b = bool(nile.get("fired")) and nile.get("hit", False)
nocp = {r["name"]: r["fired"] for r in val if r["name"] in ("bank", "quality_control_5")}
downs = [r["name"] for r in fired_ann if r["sign"] < 0 and r["hit"]]
pb2a = hr is not None and hr >= 0.60
pb2a_kill = hr is not None and hr <= 0.40
ck["verdicts"] = dict(n_val=len(val), n_fired_ann=len(fired_ann), hits=hits, hit_rate=hr,
                      PB2a=bool(pb2a), PB2a_killed=bool(pb2a_kill), PB2b_nile=bool(pb2b),
                      nocp_fired=nocp, down_steps=downs)
json.dump(ck, open(CK, "w"), default=float)
print(f"\nP-B2a: попаданий {hits}/{len(fired_ann)} горящих аннотированных ({(hr or 0)*100:.0f}%) -> "
      f"{'ПОДТВЕРЖДЁН' if pb2a else ('УБИТ' if pb2a_kill else 'не установлен')}")
print(f"P-B2b (nile): {'ПОДТВЕРЖДЁН' if pb2b else 'МИМО/тихо'} (k*={nile.get('k')}, p={nile.get('p')})")
print(f"P-B2c (без-разладочные молчат): {nocp}")
print(f"ступени ВНИЗ (смерти уровней) среди попаданий: {downs}")
print(f"[{time.time()-t0:.0f}s] -> {CK}")
