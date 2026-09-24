"""VER-002 — atlas source-confound check. Per PREREG (frozen 2026-08-31).
(a) within-source permutation null; (b) drop-COVID with own global null; (c) descriptive source-silhouette."""
import json
import numpy as np

RNG = np.random.default_rng(20260831)

# ---- rebuild points exactly as uni05_08_run.py ----
pts = []
def add(S, z, lab, src):
    if lab not in ("фолд", "непрерывный", "осциллятор"): return
    s = 1.0 if S is None else max(float(S), 1e-3)
    pts.append((np.log10(s), float(z), lab, src))

c6 = json.load(open("/home/claude/pre006c_results.json"))
for r in c6["percase"]:
    add(r.get("S"), r["R2"], {"fold": "фолд", "trans": "непрерывный", "hopf": "осциллятор"}[r["label"]] if r["label"] in ("fold", "trans", "hopf") else r["label"], "CME-тест")
e1 = json.load(open("/home/claude/ext001_ckpt.json"))["ngrip"]
full = {"YD/PB", "GI-1", "GI-2", "GI-4", "GI-7", "GI-8", "GI-11", "GI-12", "GI-13", "GI-15", "GI-16"}
for e in e1["events"]:
    if e.get("name") in full and "z" in e: add(e.get("S"), e["z"], e["label"], "NGRIP")
e34 = json.load(open("/home/claude/ext003_004_results.json"))
for e in e34["ext003"]["events"]:
    if "z" in e: add(e.get("S"), e["z"], e["label"], "палео")
for e in e34["ext004"]["res"]["Mo [ppm]"]["events"]:
    if "z" in e: add(e.get("S"), e["z"], e["label"], "аноксия")
e6 = json.load(open("/home/claude/ext005_014_ckpt.json"))["e006"]
for e in e6["rows"]:
    if "z" in e: add(e.get("S"), e["z"], e["label"], "COVID")

X = np.array([[p[0], p[1]] for p in pts])
labs = np.array([p[2] for p in pts])
srcs = np.array([p[3] for p in pts])
classes = [c for c in ("фолд", "непрерывный", "осциллятор") if (labs == c).sum() >= 5]
mask = np.isin(labs, classes)
X, labs, srcs = X[mask], labs[mask], srcs[mask]
Xs = (X - X.mean(0)) / X.std(0)

def silhouette(Xs, labs):
    from scipy.spatial.distance import cdist
    D = cdist(Xs, Xs)
    s = []
    for i in range(len(labs)):
        own = D[i][(labs == labs[i])]; a = own[own > 0].mean() if (own > 0).any() else 0
        b = min(D[i][labs == c].mean() for c in set(labs) if c != labs[i])
        s.append((b - a) / max(a, b))
    return float(np.mean(s))

sil = silhouette(Xs, labs)
stored = json.load(open("/home/claude/uni05_08_results.json"))["uni05"]
san = abs(sil - stored["sil"]) < 1e-9 and len(labs) == stored["n"]
print(f"санити пересборки: n={len(labs)} (было {stored['n']}), sil={sil:.6f} (было {stored['sil']:.6f}) -> {'OK' if san else 'РАСХОЖДЕНИЕ'}")

# ---- (a) within-source permutation ----
def within_perm():
    lp = labs.copy()
    for s0 in set(srcs):
        m = srcs == s0
        lp[m] = RNG.permutation(lp[m])
    return lp

null_w = [silhouette(Xs, within_perm()) for _ in range(1000)]
p99w = float(np.percentile(null_w, 99)); medw = float(np.median(null_w))
pv2a = sil > p99w
pv2a_kill = sil < medw
frac_above = float(np.mean([sil > q for q in null_w]))
print(f"(а) внутри-источниковый нуль: P99={p99w:.3f} мед={medw:.3f} | реальный {sil:.3f} "
      f"-> {'ВЫШЕ P99 ✓' if pv2a else ('НИЖЕ МЕДИАНЫ — УБИТ' if pv2a_kill else 'между медианой и P99 — не установлен')} "
      f"(доля нулей ниже реального: {frac_above:.3f})")

# ---- (b) drop-COVID ----
m2 = srcs != "COVID"
X2, l2 = Xs[m2], labs[m2]
cls2 = [c for c in ("фолд", "непрерывный", "осциллятор") if (l2 == c).sum() >= 5]
mm = np.isin(l2, cls2)
X2, l2 = X2[mm], l2[mm]
sil2 = silhouette(X2, l2)
null2 = [silhouette(X2, RNG.permutation(l2)) for _ in range(1000)]
p99_2 = float(np.percentile(null2, 99)); med2 = float(np.median(null2))
pv2b = sil2 > p99_2
pv2b_kill = sil2 < med2
by2 = {c: int((l2 == c).sum()) for c in cls2}
print(f"(б) без COVID: n={len(l2)} {by2} | sil={sil2:.3f} против P99={p99_2:.3f} (мед {med2:.3f}) "
      f"-> {'✓' if pv2b else ('УБИТ' if pv2b_kill else 'не установлен')}")

# ---- (c) descriptive: source-silhouette ----
sil_src = silhouette(Xs, srcs)
print(f"(в) описательное: silhouette ПО ИСТОЧНИКУ = {sil_src:.3f} (по меткам {sil:.3f})")

# ---- LOO by source (recompute) ----
loo = {}
for s0 in set(srcs):
    m = srcs != s0
    ll = labs[m]
    cl = [c for c in ("фолд", "непрерывный", "осциллятор") if (ll == c).sum() >= 5]
    mm2 = np.isin(ll, cl)
    loo[s0] = silhouette(Xs[m][mm2], ll[mm2])
print(f"LOO по источникам: " + ", ".join(f"без {k}: {v:.3f}" for k, v in loo.items()))

json.dump(dict(sanity=bool(san), sil=sil, null_within=dict(p99=p99w, med=medw, frac_below_real=frac_above),
               PV2a=bool(pv2a), PV2a_killed=bool(pv2a_kill),
               drop_covid=dict(n=len(l2), by=by2, sil=sil2, p99=p99_2, med=med2,
                               PV2b=bool(pv2b), PV2b_killed=bool(pv2b_kill)),
               sil_by_source=sil_src, loo=loo),
          open("/home/claude/ver002_results.json", "w"), default=float)
print("-> ver002_results.json")
