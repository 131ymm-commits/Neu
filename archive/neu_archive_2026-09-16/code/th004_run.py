"""TH-004 — cost of the refusal state for the atlas. Per PREREG (frozen 2026-09-02).
Cell test on EXTENDED post-onset windows; labels are NOT recomputed."""
import json, time
import numpy as np
import pandas as pd

exec(open("/home/claude/ext001_run.py").read().split("t0 = time.time()")[0])   # feats, classify, ONSETS, XLS, LAG_R2
TH6 = json.load(open("/home/claude/pre006c_thresholds.json"))
RISE_QUIET, THG = 50.0, 0.5
E_N_EXT = 60          # early segment for MAD on external windows (frozen: 60 of ~140-180 samples)
t0 = time.time()

def cell_stats(x, i_on):
    """rise (noise proxy) and G1 (protocol proxy) on the EXTENDED window."""
    x = np.asarray(x, float); n = len(x)
    e = x[:max(i_on - 5, 10)]
    t = np.arange(len(e)); res = e - np.polyval(np.polyfit(t, e, 1), t)
    sE = 1.4826 * np.median(np.abs(res - np.median(res))) + 1e-12
    medE = float(np.median(e)); late = float(np.median(x[-max(n // 10, 5):]))
    rise = (late - medE) / sE
    jump = late - medE
    if abs(jump) < 1e-12: return float(rise), None
    tail = x[int(0.6 * n):]
    tt = np.arange(len(tail), dtype=float)
    g1 = float(np.polyfit(tt, tail, 1)[0] * len(tail) / jump)
    return float(rise), g1

rows = []
# ---------------- NGRIP: extended post 1200 yr (60 samples) ----------------
import xlrd
wb = xlrd.open_workbook(XLS); sh = wb.sheet_by_index(0)
ages, d18 = [], []
for r in range(61, sh.nrows):
    a, d = sh.cell_value(r, 0), sh.cell_value(r, 2)
    if isinstance(a, float) and isinstance(d, float):
        ages.append(a); d18.append(d)
ages = np.array(ages); d18 = np.array(d18)
o = np.argsort(-ages); ages, d18 = ages[o], d18[o]
names = sorted(ONSETS, key=lambda k: -ONSETS[k])
older = {nm: (60000.0 if i == 0 else ONSETS[names[i - 1]]) for i, nm in enumerate(names)}
stored = {e["name"]: e for e in json.load(open("/home/claude/ext001_ckpt.json"))["ngrip"]["events"]}
for nm in names:
    on = ONSETS[nm]; pre = min(1600, older[nm] - 200 - on)
    if pre < 800: continue
    m = (ages <= on + pre) & (ages >= on - 1200)
    w = d18[m]
    if len(w) < 60: continue
    i_on = int(np.argmin(np.abs(ages[m] - on)))
    rise, g1 = cell_stats(w, i_on)
    rows.append(dict(src="NGRIP", name=nm, label=stored.get(nm, {}).get("label"), rise=rise, G1=g1, n=len(w)))
print(f"NGRIP: {len(rows)} событий с удлинённым хвостом [{time.time()-t0:.0f}s]", flush=True)

# ---------------- COVID: extended post 100 samples ----------------
c = pd.read_csv("/home/claude/COVID-19/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv")
g = c.groupby("Country/Region").sum(numeric_only=True)
g = g[[col for col in g.columns if "/" in col]]
top = g.iloc[:, -1].sort_values(ascending=False).head(20).index.tolist()
cov_lab = {r["country"]: r["label"] for r in json.load(open("/home/claude/ext005_014_ckpt.json"))["e006"]["rows"]}
v2_lab = {r["country"]: r["v2"] for r in json.load(open("/home/claude/pre010b_ckpt.json"))["covid"]["rows"]}
for cn in top:
    cum = g.loc[cn].to_numpy(float)
    new = np.clip(np.diff(cum, prepend=0), 0, None)
    sm = pd.Series(new).rolling(7, min_periods=1).mean().to_numpy()
    on = np.flatnonzero(sm >= 50)
    if on.size == 0: continue
    i0 = int(on[0]); lo = i0 - 40
    w = sm[max(lo, 0): i0 + 100]
    if lo < 0: w = np.concatenate([np.zeros(-lo), w])
    if len(w) < 100: continue
    rise, g1 = cell_stats(w, 40)
    rows.append(dict(src="COVID", name=cn, label=v2_lab.get(cn, cov_lab.get(cn)), rise=rise, G1=g1, n=len(w)))
print(f"COVID: добавлено, всего {len(rows)} [{time.time()-t0:.0f}s]", flush=True)

# ---------------- verdicts ----------------
def refused(r):
    return bool(r["rise"] < RISE_QUIET and r["G1"] is not None and r["G1"] < THG)
for r in rows: r["refused"] = refused(r)
by = {}
for s in ("NGRIP", "COVID"):
    sub = [r for r in rows if r["src"] == s]
    by[s] = dict(n=len(sub), refused=sum(1 for r in sub if r["refused"]),
                 quiet=sum(1 for r in sub if r["rise"] >= RISE_QUIET))
n_all = len(rows); n_ref = sum(1 for r in rows if r["refused"])
frac = n_ref / max(n_all, 1)
pt4a = frac <= 0.40; pt4a_kill = frac > 0.70
grok = json.load(open("/home/claude/grok001_ckpt.json"))
grok_rows = [v for k, v in grok.items() if isinstance(v, dict) and v.get("born") and v.get("rise") is not None]
g_quiet = sum(1 for v in grok_rows if v["rise"] >= RISE_QUIET)
pt4b = g_quiet == len(grok_rows) and len(grok_rows) >= 12
pt4b_kill = (len(grok_rows) - g_quiet) >= 3
print(f"\nпо источникам: {by}")
print(f"P-T4a: отказано {n_ref}/{n_all} = {frac*100:.0f}% -> "
      f"{'ПОДТВЕРЖДЁН' if pt4a else ('УБИТ' if pt4a_kill else 'не установлен')}")
print(f"P-T4b (гроккинг вне клетки отказа): тихих {g_quiet}/{len(grok_rows)} (rise медиана "
      f"{np.median([v['rise'] for v in grok_rows]):.0f}) -> {'ПОДТВЕРЖДЁН' if pt4b else ('УБИТ' if pt4b_kill else 'не установлен')}")
for r in rows:
    if r["refused"]:
        print(f"  отказ: {r['src']}/{r['name']} (метка была «{r['label']}», rise={r['rise']:.1f}, G1={r['G1']:.2f})")
json.dump(dict(rows=rows, by=by, n_ref=n_ref, n_all=n_all, frac=frac,
               PT4a=bool(pt4a), PT4a_killed=bool(pt4a_kill),
               grok_quiet=g_quiet, grok_n=len(grok_rows), PT4b=bool(pt4b), PT4b_killed=bool(pt4b_kill)),
          open("/home/claude/th004_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> th004_results.json")
