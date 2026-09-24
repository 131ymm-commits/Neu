"""PYTHIA-001 library: loading Pythia v1 zero-shot evals; step-vs-ramp certificate on the 27-node log-step grid; birth step."""
import json, glob, os, re
import numpy as np
ROOT = "/home/claude/pythia_repo/evals/pythia-v1"
STD = ["pythia-70m", "pythia-160m", "pythia-410m", "pythia-1b-deduped", "pythia-1.4b", "pythia-2.8b", "pythia-6.9b", "pythia-12b"]
DED = ["pythia-70m-deduped", "pythia-160m-deduped", "pythia-410m-deduped", "pythia-1b-deduped", "pythia-1.4b-deduped", "pythia-2.8b-deduped", "pythia-6.9b-deduped", "pythia-12b-deduped"]
SIZE = {"pythia-70m": 70e6, "pythia-160m": 160e6, "pythia-410m": 410e6, "pythia-1b-deduped": 1e9, "pythia-1.4b": 1.4e9, "pythia-2.8b": 2.8e9, "pythia-6.9b": 6.9e9, "pythia-12b": 12e9,
        "pythia-70m-deduped": 70e6, "pythia-160m-deduped": 160e6, "pythia-410m-deduped": 410e6, "pythia-1.4b-deduped": 1.4e9, "pythia-2.8b-deduped": 2.8e9, "pythia-6.9b-deduped": 6.9e9, "pythia-12b-deduped": 12e9}
TASKS = ["arc_easy", "arc_challenge", "piqa", "winogrande", "wsc", "sciq", "logiqa", "lambada_openai"]
CHANCE = {"arc_easy": 0.25, "arc_challenge": 0.25, "piqa": 0.5, "winogrande": 0.5, "wsc": 0.5, "sciq": 0.25, "logiqa": 0.25, "lambada_openai": 0.0}

def load_model(m):
    fs = glob.glob(f"{ROOT}/{m}/zero-shot/*.json")
    rows = []
    for f in fs:
        st = int(re.search(r"step(\d+)", os.path.basename(f)).group(1))
        d = json.load(open(f))["results"]
        rows.append((st, d))
    rows.sort(key=lambda r: r[0])
    steps = np.array([r[0] for r in rows], float)
    def series(task, metric):
        return np.array([r[1][task][metric] if task in r[1] and metric in r[1][task] else np.nan for r in rows], float)
    mm = [k for k in rows[0][1] if k.startswith("hendrycksTest")]
    mmlu = np.array([np.mean([r[1][k]["acc"] for k in mm if k in r[1]]) for r in rows], float)
    return steps, series, mmlu

def fit_step(x, y):
    n = len(y); best = (np.inf, None)
    for k in range(2, n - 1):
        sse = ((y[:k] - y[:k].mean()) ** 2).sum() + ((y[k:] - y[k:].mean()) ** 2).sum()
        if sse < best[0]: best = (sse, k)
    sse, k = best
    return n * np.log(max(sse, 1e-12) / n) + 3 * np.log(n), k, sse

def fit_ramp(x, y):
    """continuous piecewise-linear with two breakpoints (plateau-ramp-plateau allowed but slopes free): params 4 + 2 breakpoints."""
    n = len(y); best = (np.inf, None)
    for i in range(1, n - 3):
        for j in range(i + 2, n - 1):
            a, b = x[i], x[j]
            X = np.column_stack([np.ones(n), x, np.maximum(x - a, 0), np.maximum(x - b, 0)])
            beta, *_ = np.linalg.lstsq(X, y, rcond=None)
            sse = float(((y - X @ beta) ** 2).sum())
            if sse < best[0]: best = (sse, (i, j))
    sse, br = best
    return n * np.log(max(sse, 1e-12) / n) + 6 * np.log(n), br, sse

def certificate(steps, y, chance, gain_min=0.05):
    """Returns dict: label in {нет рождения, ступень, плавный, неразличимо}, birth (log10 step), gain."""
    m = ~np.isnan(y); x = np.log10(steps[m] + 1); y = y[m]
    final = y[-3:].mean(); gain = final - chance
    out = dict(gain=float(gain), final=float(final), n=int(len(y)))
    if gain < gain_min:
        out["label"] = "нет рождения"; out["birth"] = None; return out
    bs, ks, ss = fit_step(x, y); br, kr, sr = fit_ramp(x, y)
    d = br - bs   # positive → step better
    out.update(dbic=float(d), k_step=int(ks), br_ramp=[int(kr[0]), int(kr[1])])
    out["label"] = "ступень" if d >= 6 else ("плавный" if d <= -6 else "неразличимо")
    thr = chance + 0.5 * gain
    idx = np.flatnonzero(y >= thr)
    # first sustained crossing: y >= thr and stays >= thr for the rest? use first crossing after which the median of the remainder >= thr
    b = None
    for i in idx:
        if np.median(y[i:]) >= thr:
            b = i; break
    if b is None or b == 0:
        out["birth"] = float(x[0]) if b == 0 else None
    else:
        x0, x1, y0, y1 = x[b - 1], x[b], y[b - 1], y[b]
        out["birth"] = float(x0 + (thr - y0) / (y1 - y0) * (x1 - x0)) if y1 != y0 else float(x1)
    return out
