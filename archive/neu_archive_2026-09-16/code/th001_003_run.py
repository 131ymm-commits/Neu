"""TH-001/002/003 — validity cells of the transient certificate, cell readability, rule v3 with refusal.
Per PREREG (frozen 2026-09-02). Frozen instrument: PRE-006c features and thresholds."""
import json, os, time
import numpy as np

exec(open("/home/claude/pre006c_run.py").read().split("t0 = time.time()")[0])   # SYS, features, feat_S, feat_rise_sE, feat_R2, E_N, T_TOT, REC_DT
TH = json.load(open("/home/claude/pre006c_thresholds.json"))
RISE_QUIET, THG = 50.0, 0.5
k1s, k4s = 5.75, 8.75; SN1, Ww = 1.37154, 4.00578 - 1.37154
EPSV, KCAP = 0.1, 5.0
CK = "/home/claude/th001_003_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()

def par_ramp(p0, p1):
    return lambda t: p0 + (p1 - p0) * min(t / T_TOT, 1.0)
def par_park(p0, thr, eps, t_thr=300.0):
    v = (thr - p0) / t_thr; p1 = thr + eps * (thr - p0)
    return lambda t: min(p0 + v * t, p1)

def G1(x):
    n = len(x)
    e = float(np.median(x[:E_N])); late = float(np.median(x[-n // 10:]))
    jump = late - e
    if abs(jump) < 1e-9: return None
    tail = x[int(0.6 * n):].astype(float)
    t = np.arange(len(tail), dtype=float)
    return float(np.polyfit(t, tail, 1)[0] * len(tail) / jump)

def mf(kind, eps, dt=0.002, T=600.0, t_thr=300.0):
    p0, thr = (0.30, 1.0) if kind == "fold" else (0.50, 1.0)
    v = (thr - p0) / t_thr; p1 = thr + eps * (thr - p0)
    if kind == "fold":
        rts = np.roots([-1.0, k1s, -k4s, SN1 + p0 * Ww]); x = float(np.sort(rts[np.isreal(rts)].real)[0])
    else:
        x = float((-(1 - p0) + np.sqrt((1 - p0) ** 2 + 4 * EPSV / KCAP)) / (2 / KCAP))
    n = int(T / dt); stride = int(REC_DT / dt); rec = np.empty(int(T / REC_DT)); k = 0
    for i in range(n):
        par = min(p0 + v * i * dt, p1)
        dx = ((SN1 + par * Ww) + k1s * x * x - x ** 3 - k4s * x) if kind == "fold" else (par * x + EPSV - x - x * x / KCAP)
        x += dt * dx
        if (i + 1) % stride == 0 and k < len(rec):
            rec[k] = x; k += 1
    return rec

def rowof(x, cell, kind, tag):
    f = features(x)
    g = G1(x)
    return dict(cell=cell, truth=kind, tag=tag, S=f["S"], rise=f["rise"], R2=f["R2"], G1=g)

# ---------------- records ----------------
if "rows" not in ck:
    rows = []
    for kind, off in (("fold", 0), ("trans", 500)):
        S_ = SYS[kind]; p0, thr, p1o = S_["p0"], S_["thr"], S_["p1"]
        rec = S_["sim"](par_ramp(p0, p1o), 861000 + off, 6)
        for r in range(6):
            rows.append(rowof(rec[r], "шум+рамп", kind, f"r{r}"))
        for eps in (0.15, 0.03):
            rec = S_["sim"](par_park(p0, thr, eps), 862000 + off + int(eps * 1000), 6)
            for r in range(6):
                rows.append(rowof(rec[r], "шум+парковка", kind, f"e{eps}r{r}"))
        print(f"{kind}: стохастика готова [{time.time()-t0:.0f}s]", flush=True)
        for eps in (0.30, 0.15, 0.07, 0.03):
            rows.append(rowof(mf(kind, eps), "детерм+парковка", kind, f"mf{eps}"))
        print(f"{kind}: детерминированные готовы [{time.time()-t0:.0f}s]", flush=True)
    ck["rows"] = rows
    json.dump(ck, open(CK, "w"), default=float)
rows = ck["rows"]

def Ss(cell, kind):
    return [r["S"] for r in rows if r["cell"] == cell and r["truth"] == kind and r["S"] is not None]

# ---------------- TH-001 ----------------
v = {}
for cell in ("шум+рамп", "шум+парковка", "детерм+парковка"):
    sf, st = Ss(cell, "fold"), Ss(cell, "trans")
    alive = bool(sf and st and min(sf) > max(st))
    gap = (min(sf) / max(st)) if (sf and st and max(st) > 0) else None
    v[cell] = dict(n_fold=len(sf), n_trans=len(st), min_fold=min(sf) if sf else None, max_trans=max(st) if st else None,
                   med_fold=float(np.median(sf)) if sf else None, med_trans=float(np.median(st)) if st else None,
                   alive=alive, gap=gap)
    print(f"{cell}: фолд S мед={v[cell]['med_fold']} (min {v[cell]['min_fold']}) | транс мед={v[cell]['med_trans']} "
          f"(max {v[cell]['max_trans']}) -> разделение {'ЖИВО' if alive else 'мертво'} зазор={None if gap is None else round(gap,2)}", flush=True)
c1, c2, c3 = v["шум+рамп"], v["шум+парковка"], v["детерм+парковка"]
pt1a = c1["alive"]
pt1b = (not c2["alive"]) and (c2["med_trans"] is not None and c2["med_fold"] is not None and c2["med_trans"] >= 0.5 * c2["med_fold"])
pt1c = c3["alive"] and (c3["gap"] is not None and c3["gap"] >= 5)
print(f"P-T1a (рамп+шум разделяет): {'ПОДТВЕРЖДЁН' if pt1a else 'УБИТ'}")
print(f"P-T1b (парковка+шум НЕ разделяет и класс поднялся): {'ПОДТВЕРЖДЁН' if pt1b else 'УБИТ'}")
print(f"P-T1c (парковка+детерминизм разделяет с зазором ≥×5): {'ПОДТВЕРЖДЁН' if pt1c else 'УБИТ'}")

# ---------------- TH-002 ----------------
stoch = [r for r in rows if r["cell"].startswith("шум")]
det = [r for r in rows if r["cell"].startswith("детерм")]
q_st = float(np.mean([r["rise"] < RISE_QUIET for r in stoch]))
q_dt = float(np.mean([r["rise"] >= RISE_QUIET for r in det]))
ramp = [r for r in rows if r["cell"] == "шум+рамп" and r["G1"] is not None]
park = [r for r in rows if r["cell"] == "шум+парковка" and r["G1"] is not None]
g_ramp = sum(1 for r in ramp if r["G1"] >= THG); g_park = sum(1 for r in park if r["G1"] < THG)
pt2a = q_st >= 0.9 and q_dt >= 0.9
pt2a_kill = q_st < 0.7 or q_dt < 0.7
pt2b = g_ramp >= 8 and g_park >= 15
pt2b_kill = (g_ramp / max(len(ramp), 1) <= 0.5) or (g_park / max(len(park), 1) <= 0.5)
print(f"\nP-T2a (rise как прокси шума): стохастика <50 в {q_st*100:.0f}%, детерминизм ≥50 в {q_dt*100:.0f}% -> "
      f"{'ПОДТВЕРЖДЁН' if pt2a else ('УБИТ' if pt2a_kill else 'не установлен')}")
print(f"P-T2b (G1 как прокси протокола): рамп {g_ramp}/{len(ramp)} ≥0.5, парковка {g_park}/{len(park)} <0.5 -> "
      f"{'ПОДТВЕРЖДЁН' if pt2b else ('УБИТ' if pt2b_kill else 'не установлен')}")

# ---------------- TH-003: rule v3 ----------------
def rule_v3(r):
    if r["R2"] >= TH["thR2"]: return "осциллятор"
    if r["rise"] < TH["thRise"]: return "нет рождения"
    if r["rise"] < RISE_QUIET and (r["G1"] is not None and r["G1"] < THG): return "не читается"
    if r["S"] is not None and r["S"] >= TH["thS"]: return "фолд"
    return "непрерывный"

MAP = {"fold": "фолд", "trans": "непрерывный", "hopf": "осциллятор"}
c6 = json.load(open("/home/claude/ver001c_ckpt.json"))["percase"]     # frozen fresh ramp test set (needs G1 → recompute below)
if "vc" not in ck:
    vc = []
    for case in c6:
        x = gen(case["truth"], True, 970000 + OFF[case["truth"]] + case["i"])
        vc.append(rowof(x, "шум+рамп(VER-001c)", case["truth"], f"i{case['i']}"))
        print(f"VER-001c пересчёт {case['truth']}#{case['i']}: G1={vc[-1]['G1'] if vc[-1]['G1'] is None else round(vc[-1]['G1'],2)} [{time.time()-t0:.0f}s]", flush=True)
    ck["vc"] = vc
    json.dump(ck, open(CK, "w"), default=float)
vc = ck["vc"]
a_lab = [(r["truth"], rule_v3(r)) for r in vc]
a_ok = sum(1 for t_, l in a_lab if l == MAP[t_])
a_ref = sum(1 for _, l in a_lab if l == "не читается")
b = [r for r in rows if r["cell"] == "шум+парковка"]
b_ref = sum(1 for r in b if rule_v3(r) == "не читается")
d = [r for r in rows if r["cell"] == "детерм+парковка"]
d_ok = sum(1 for r in d if rule_v3(r) == MAP[r["truth"]]); d_ref = sum(1 for r in d if rule_v3(r) == "не читается")
pt3a = a_ok >= 12 and a_ref <= 1
pt3a_kill = a_ok <= 10 or a_ref >= 4
pt3b = b_ref >= 16; pt3b_kill = b_ref <= 6
pt3c = d_ok >= 7 and d_ref == 0; pt3c_kill = d_ref >= 3
print(f"\nP-T3a (родная клетка не пострадала): верных {a_ok}/15, отказов {a_ref}/15 -> "
      f"{'ПОДТВЕРЖДЁН' if pt3a else ('УБИТ' if pt3a_kill else 'не установлен')}")
print(f"P-T3b (правило кусает в клетке отказа): отказов {b_ref}/24 -> "
      f"{'ПОДТВЕРЖДЁН' if pt3b else ('УБИТ' if pt3b_kill else 'не установлен')}")
print(f"P-T3c (детерминированная парковка не перекрыта): верных {d_ok}/8, отказов {d_ref} -> "
      f"{'ПОДТВЕРЖДЁН' if pt3c else ('УБИТ' if pt3c_kill else 'не установлен')}")

ck["verdicts"] = dict(cells=v, PT1a=bool(pt1a), PT1b=bool(pt1b), PT1c=bool(pt1c),
                      q_st=q_st, q_dt=q_dt, PT2a=bool(pt2a), PT2a_killed=bool(pt2a_kill),
                      g_ramp=g_ramp, n_ramp=len(ramp), g_park=g_park, n_park=len(park),
                      PT2b=bool(pt2b), PT2b_killed=bool(pt2b_kill),
                      a_ok=a_ok, a_ref=a_ref, b_ref=b_ref, d_ok=d_ok, d_ref=d_ref,
                      PT3a=bool(pt3a), PT3a_killed=bool(pt3a_kill), PT3b=bool(pt3b), PT3b_killed=bool(pt3b_kill),
                      PT3c=bool(pt3c), PT3c_killed=bool(pt3c_kill))
json.dump(ck, open(CK, "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> {CK}")
