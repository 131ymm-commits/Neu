"""PRE-010b part 2 — atlas v2 + e006 controls v2 + LOO. Per PREREG P-P10b3 (frozen 2026-08-31)."""
import json
import numpy as np

RNG = np.random.default_rng(20260832)
ckb = json.load(open("/home/claude/pre010b_ckpt.json"))
v2map = {r["country"]: r["v2"] for r in ckb["covid"]["rows"]}

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
    if "z" in e:
        lab = ckb["paleo8"]["v2"] if e.get("tsid") == 8 else e["label"]     # v2 relabel tsid8
        add(e.get("S"), e["z"], lab, "палео")
for e in e34["ext004"]["res"]["Mo [ppm]"]["events"]:
    if "z" in e: add(e.get("S"), e["z"], e["label"], "аноксия")
for e in json.load(open("/home/claude/ext005_014_ckpt.json"))["e006"]["rows"]:
    if "z" in e: add(e.get("S"), e["z"], v2map.get(e["country"], e["label"]), "COVID")   # v2 relabel

X = np.array([[p[0], p[1]] for p in pts])
labs = np.array([p[2] for p in pts])
srcs = np.array([p[3] for p in pts])
classes = [c for c in ("фолд", "непрерывный", "осциллятор") if (labs == c).sum() >= 5]
mask = np.isin(labs, classes)
X, labs, srcs = X[mask], labs[mask], srcs[mask]
Xs = (X - X.mean(0)) / X.std(0)
by = {c: int((labs == c).sum()) for c in classes}
print(f"атлас v2: n={len(labs)} {by} (классы <5 точек исключены: {[c for c in ('фолд','непрерывный','осциллятор') if c not in classes]})")

def silhouette(Xs, labs):
    from scipy.spatial.distance import cdist
    D = cdist(Xs, Xs)
    s = []
    for i in range(len(labs)):
        own = D[i][(labs == labs[i])]; a = own[own > 0].mean() if (own > 0).any() else 0
        b = min(D[i][labs == c].mean() for c in set(labs) if c != labs[i])
        s.append((b - a) / max(a, b))
    return float(np.mean(s))

sil2 = silhouette(Xs, labs)
null_g = [silhouette(Xs, RNG.permutation(labs)) for _ in range(1000)]
p99g, medg = float(np.percentile(null_g, 99)), float(np.median(null_g))
def within_perm():
    lp = labs.copy()
    for s0 in set(srcs):
        m = srcs == s0
        lp[m] = RNG.permutation(lp[m])
    return lp
null_w = [silhouette(Xs, within_perm()) for _ in range(1000)]
p99w, medw = float(np.percentile(null_w, 99)), float(np.median(null_w))
pb3 = sil2 >= 0.365 and sil2 > p99g and sil2 > p99w
pb3_kill = sil2 < medg
print(f"P-P10b3: sil_v2={sil2:.3f} (v1: 0.365) | глобальный нуль P99={p99g:.3f} мед={medg:.3f} | "
      f"внутри-источниковый P99={p99w:.3f} мед={medw:.3f}")
print("вердикт: " + ("ПОДТВЕРЖДЁН" if pb3 else ("УБИТ (ниже медианы нуля — v2 отвергается, атлас v1 остаётся)" if pb3_kill else "не установлен")))

# e006 controls under v2: v2 only removes osc labels; count none as before
ctls = json.load(open("/home/claude/ext005_014_ckpt.json"))["e006"]["ctls"]
n_none_v1 = sum(1 for x in ctls if x["label"] == "нет рождения")
n_osc_ctl = sum(1 for x in ctls if x["label"] == "осциллятор")
print(f"контроли e006: v1 none {n_none_v1}/{len(ctls)}, осц-контролей {n_osc_ctl} (v2 не понижает 'none' по построению)")

# LOO by country on losses
lost = set(ckb["verdicts_b12"]["lost"])
loo_min = min(len(lost - {c}) for c in lost)
print(f"LOO по странам: минимум потерь при выпадении любой страны = {loo_min} (кромка P-P10b1 ≥ 3 держится: {loo_min >= 3})")

json.dump(dict(by=by, sil2=sil2, null_g=dict(p99=p99g, med=medg), null_w=dict(p99=p99w, med=medw),
               PP10b3=bool(pb3), PP10b3_killed=bool(pb3_kill), ctl_none_v1=n_none_v1, ctl_osc=n_osc_ctl,
               loo_min_lost=loo_min,
               points=[dict(x=float(a), z=float(b), lab=l, src=s) for (a, b), l, s in zip(X, labs, srcs)]),
          open("/home/claude/pre010b2_results.json", "w"), default=float)
print("-> pre010b2_results.json")
