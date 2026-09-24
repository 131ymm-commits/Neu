"""UNI-05 atlas + UNI-08 thermoacoustic rate shift. Per PREREG (frozen 2026-08-27)."""
import json, glob, re
import numpy as np

RNG = np.random.default_rng(424245)
out = {}

# ---------------- UNI-05 atlas ----------------
pts = []   # (log10 S, z, label, source)
def add(S, z, lab, src):
    if lab not in ("фолд", "непрерывный", "осциллятор"): return
    s = 1.0 if S is None else max(float(S), 1e-3)
    pts.append((np.log10(s), float(z), lab, src))

c6 = json.load(open("/home/claude/pre006c_results.json"))
for r in c6["percase"]:
    add(r.get("S"), r["R2"], {"fold": "фолд", "trans": "непрерывный", "hopf": "осциллятор"}[r["label"]] if r["label"] in ("fold","trans","hopf") else r["label"], "CME-тест")
e1 = json.load(open("/home/claude/ext001_ckpt.json"))["ngrip"]
full = {"YD/PB","GI-1","GI-2","GI-4","GI-7","GI-8","GI-11","GI-12","GI-13","GI-15","GI-16"}
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
null = [silhouette(Xs, RNG.permutation(labs)) for _ in range(1000)]
p99 = float(np.percentile(null, 99)); med = float(np.median(null))
pua1 = sil > p99; pua1_kill = sil < med
loo_ok = all(silhouette(Xs[srcs != s0], labs[srcs != s0]) > 0 for s0 in set(srcs))
out["uni05"] = dict(n=len(labs), by_class={c: int((labs == c).sum()) for c in classes},
                    sil=sil, null_p99=p99, null_med=med, PUA1=bool(pua1), PUA1_killed=bool(pua1_kill),
                    loo_ok=bool(loo_ok),
                    points=[dict(x=float(a), z=float(b), lab=l, src=s) for (a, b), l, s in zip(X, labs, srcs)])
print(f"UNI-05: n={len(labs)} {out['uni05']['by_class']} | silhouette={sil:.3f} против нуля P99={p99:.3f} (мед {med:.3f}) "
      f"-> {'ПОДТВЕРЖДЁН' if pua1 else ('УБИТ' if pua1_kill else 'не установлен')} (LOO>0: {loo_ok})", flush=True)

# ---------------- UNI-08 thermo rate shift ----------------
base = "/home/claude/deep-early-warnings-pnas/test_empirical/thermoacoustic/data/thermo_experiments/Rate dependent transitions/pressure data"
log = open(f"{base}/log.txt", encoding="latin-1").read()
rates = {}
for m in re.finditer(r"(\d+)\.txt\s*[-:–]*\s*.*?([\d.]+)\s*mV", log):
    rates[int(m.group(1))] = float(m.group(2))
if not rates:
    for ln in log.splitlines():
        m = re.match(r"\s*(\d+)[\).: ]+.*?([\d.]+)\s*mV/s", ln)
        if m: rates[int(m.group(1))] = float(m.group(2))
rows = []
for fp in sorted(glob.glob(f"{base}/[0-9]*.txt"), key=lambda s: int(re.findall(r"(\d+)\.txt", s)[0])):
    idx = int(re.findall(r"(\d+)\.txt", fp)[0])
    if idx not in rates: continue
    try:
        d = np.loadtxt(fp, encoding="latin-1")
    except Exception:
        continue
    if d.ndim != 2 or d.shape[1] < 2: continue
    t, p = d[:, 0], d[:, 1]
    dt = np.median(np.diff(t[:1000]))
    wlen = max(int(0.5 / dt), 10)
    nw = len(p) // wlen
    rms = np.sqrt(np.mean(p[:nw * wlen].reshape(nw, wlen) ** 2, axis=1))
    base_r = np.median(rms[:max(nw // 10, 3)])
    hits = np.flatnonzero((rms[:-1] >= 5 * base_r) & (rms[1:] >= 5 * base_r))
    if hits.size == 0:
        rows.append(dict(idx=idx, rate=rates[idx], onset=None)); continue
    t_on = t[0] + (hits[0]) * wlen * dt
    V_on = rates[idx] / 1000.0 * t_on          # V = R[mV/s]*t
    rows.append(dict(idx=idx, rate=rates[idx], t_on=float(t_on), V_on=float(V_on),
                     flag_first=bool(hits[0] <= 1)))
ok_rows = [r for r in rows if r.get("V_on") is not None]
if len(ok_rows) >= 12:
    from scipy.stats import spearmanr
    rr = np.array([r["rate"] for r in ok_rows]); vv = np.array([r["V_on"] for r in ok_rows])
    rho = float(spearmanr(rr, vv).statistic)
    perm = [abs(float(spearmanr(rr, RNG.permutation(vv)).statistic)) for _ in range(1000)]
    p_ = float(np.mean([q >= abs(rho) for q in perm]))
    pur1 = rho > 0 and p_ < 0.05; pur1_kill = rho <= 0
else:
    rho, p_, pur1, pur1_kill = None, None, False, False
out["uni08"] = dict(n_files=len(rows), n_ok=len(ok_rows), rho=rho, p=p_,
                    PUR1=bool(pur1), PUR1_killed=bool(pur1_kill),
                    rows=[{k: v for k, v in r.items()} for r in rows])
json.dump(out, open("/home/claude/uni05_08_results.json", "w"), default=float)
print(f"UNI-08: пригодных {len(ok_rows)}/{len(rows)} | Spearman(V_onset, rate) = {rho} (p={p_}) -> "
      f"{'ПОДТВЕРЖДЁН' if pur1 else ('УБИТ' if pur1_kill else 'не установлен')}")
