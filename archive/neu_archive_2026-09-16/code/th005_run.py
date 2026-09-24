"""TH-005 — the onset-dispersion certificate. Per PREREG (frozen 2026-09-02). Fresh seeds 871000+."""
import json, time
import numpy as np
exec(open("/home/claude/pre006c_run.py").read().split("t0 = time.time()")[0])
from scipy.ndimage import median_filter

def par_park(p0, thr, eps, t_thr=300.0):
    v = (thr - p0) / t_thr; p1 = thr + eps * (thr - p0)
    return lambda t: min(p0 + v * t, p1)
def par_ramp(p0, p1):
    return lambda t: p0 + (p1 - p0) * min(t / T_TOT, 1.0)

def t_onset(x):
    x = np.asarray(x, float); n = len(x)
    e = float(np.median(x[:E_N])); late = float(np.median(x[-n // 10:]))
    if late <= e: return None
    xm = median_filter(x, size=51, mode="nearest")
    hi = np.flatnonzero(xm >= e + 0.5 * (late - e))
    return None if hi.size == 0 else float(hi[0])

def cv(v):
    v = [q for q in v if q is not None]
    return (float(np.std(v) / np.mean(v)), len(v)) if len(v) >= 5 else (None, len(v))

t0 = time.time(); cells = {}
for kind, off in (("fold", 0), ("trans", 500)):
    S_ = SYS[kind]; p0, thr, p1o = S_["p0"], S_["thr"], S_["p1"]
    for pname, pf in (("рамп", par_ramp(p0, p1o)), ("парк0.15", par_park(p0, thr, 0.15)),
                      ("парк0.03", par_park(p0, thr, 0.03))):
        rec = S_["sim"](pf, 871000 + off + len(pname) * 7, 8)
        ts = [t_onset(rec[r]) for r in range(8)]
        c, n = cv(ts)
        cells[f"{kind}|{pname}"] = dict(ts=ts, cv=c, n=n)
        print(f"{kind:5s} {pname:9s}: CV={None if c is None else round(c,3)} (годных {n}/8) [{time.time()-t0:.0f}s]", flush=True)

g = json.load(open("/home/claude/grok001_ckpt.json"))
grok = {}
for arm, ss in (("main", (201, 202, 203, 204, 205, 206)), ("a30", (211, 212, 213)), ("a25", (221, 222, 223))):
    t = [g[f"{arm}_{s}"]["t_grok"] for s in ss]
    grok[arm] = float(np.std(t) / np.mean(t))
print(f"гроккинг CV: {({k: round(v,4) for k, v in grok.items()})}")

fold_cells = {k: v["cv"] for k, v in cells.items() if k.startswith("fold") and v["cv"] is not None}
driven = dict(grok)
if cells["trans|рамп"]["cv"] is not None: driven["транс+рамп"] = cells["trans|рамп"]["cv"]
pt5a = all(c >= 0.30 for c in fold_cells.values()) and all(c <= 0.15 for c in driven.values())
pt5a_kill = any(c < 0.15 for c in fold_cells.values()) or any(c > 0.30 for c in driven.values())

pf_ = [cells[f"fold|парк{e}"]["cv"] for e in ("0.15", "0.03")]
pt_ = [cells[f"trans|парк{e}"]["cv"] for e in ("0.15", "0.03")]
ok_order = all(c is not None for c in pf_ + pt_) and min(pf_) > max(pt_)
jk = 0; tot = 0
for e in ("0.15", "0.03"):
    for drop in range(8):
        fv = [q for i, q in enumerate(cells[f"fold|парк{e}"]["ts"]) if i != drop and q is not None]
        tv = [q for i, q in enumerate(cells[f"trans|парк{e}"]["ts"]) if i != drop and q is not None]
        if len(fv) < 5 or len(tv) < 5: continue
        tot += 1
        jk += (np.std(fv) / np.mean(fv)) > (np.std(tv) / np.mean(tv))
pt5b = ok_order and tot > 0 and jk / tot >= 7 / 8
pt5b_kill = not ok_order
pt5c = all(v <= 0.15 for v in grok.values()); pt5c_kill = any(v > 0.30 for v in grok.values())
print(f"\nP-T5a (часы): фолд-клетки {({k: round(v,3) for k, v in fold_cells.items()})} ≥0.30? | ведомые "
      f"{({k: round(v,3) for k, v in driven.items()})} ≤0.15? -> {'ПОДТВЕРЖДЁН' if pt5a else ('УБИТ' if pt5a_kill else 'не установлен')}")
print(f"P-T5b (CV как сертификат в клетке отказа): фолд {[round(c,3) for c in pf_]} против транс {[round(c,3) for c in pt_]}, "
      f"джекнайф {jk}/{tot} -> {'ПОДТВЕРЖДЁН' if pt5b else ('УБИТ' if pt5b_kill else 'не установлен')}")
print(f"P-T5c (гроккинг ведомый): {'ПОДТВЕРЖДЁН' if pt5c else ('УБИТ' if pt5c_kill else 'не установлен')}")
json.dump(dict(cells=cells, grok=grok, PT5a=bool(pt5a), PT5a_killed=bool(pt5a_kill),
               PT5b=bool(pt5b), PT5b_killed=bool(pt5b_kill), jk=jk, jk_tot=tot,
               PT5c=bool(pt5c), PT5c_killed=bool(pt5c_kill)),
          open("/home/claude/th005_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> th005_results.json")
