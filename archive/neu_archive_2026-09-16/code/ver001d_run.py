"""VER-001d — fresh-seed replication of migration curve (PRE-005b/PRE-008). Per PREREG (frozen 2026-08-31).
Same protocol as pre008 part A at each V in {20,200,2000}; fresh seed bases 20270854 (V=20,200), 20270855 (V=2000)."""
import json, os, time
import numpy as np

exec(open("/home/claude/pre005b_run.py").read().split("ck = json.load")[0])   # sim_ext, indicators, first_fire, drift, const
CK = "/home/claude/ver001d_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()

for V, SB in ((20, 20270854), (200, 20270854), (2000, 20270855)):
    key = f"V{V}"
    if key in ck: continue
    base = sim_ext(const, SB + V, 5, V)
    ctrl = sim_ext(const, SB + V + 77, 5, V)
    drf = sim_ext(drift, SB + V + 154, 5, V)
    allv, alla = [], []
    for r in range(5):
        for (_, v, a) in indicators(base[r]):
            allv.append(v); alla.append(a)
    fv = 2.5 * float(np.percentile(allv, 99))
    fa = min(2.5 * float(np.percentile(alla, 99)), 0.999)
    fires, leads, trans_fr = 0, [], []
    for r in range(5):
        tr = drf[r]
        cross = np.flatnonzero(tr > 2.2)
        trans_fr.append(float(drift(cross[0] * REC_DT)) if cross.size else None)
        w_, c = first_fire(indicators(tr), fv, fa)
        if c is not None and drift(c * REC_DT) < THR:
            fires += 1
            leads.append(float(THR - drift(c * REC_DT)))
    cf = sum(1 for r in range(5) if first_fire(indicators(ctrl[r]), fv, fa)[1] is not None)
    ck[key] = dict(floor_var=fv, floor_ac=fa, fires=fires, leads=leads, trans_fr=trans_fr, ctrl=cf)
    json.dump(ck, open(CK, "w"), default=float)
    print(f"V={V}: trans_fr={[(round(x,3) if x else None) for x in trans_fr]} | fires {fires}/5 | ctrl {cf}/5 [{time.time()-t0:.0f}s]", flush=True)

med = {}
for V in (20, 200, 2000):
    tf = [x for x in ck[f"V{V}"]["trans_fr"] if x is not None]
    med[V] = float(np.median(tf)) if tf else None
pv1d1 = None not in med.values() and med[20] < med[200] < med[2000]
bands = dict(V20=(med[20] is not None and 0.25 <= med[20] <= 0.55),
             V200=(med[200] is not None and 0.75 <= med[200] <= 0.95),
             V2000=(med[2000] is not None and med[2000] >= 0.90))
nb = sum(bands.values())
pv1d2 = nb == 3
pv1d2_kill = nb <= 1
f2 = ck["V2000"]["fires"]
ctl_bad = any(ck[f"V{V}"]["ctrl"] >= 2 for V in (20, 200, 2000))
pv1d3 = f2 >= 4 and not ctl_bad
pv1d3_kill = f2 <= 2 or ctl_bad
ck["verdicts"] = dict(med=med, PV1d1=bool(pv1d1), bands=bands, PV1d2=bool(pv1d2), PV1d2_killed=bool(pv1d2_kill),
                      PV1d3=bool(pv1d3), PV1d3_killed=bool(pv1d3_kill))
json.dump(ck, open(CK, "w"), default=float)
print(f"\nP-V1d1 (монотонность): {med[20]} < {med[200]} < {med[2000]} (исходно 0.38/0.85/0.985) -> {'РЕПЛИЦИРОВАН' if pv1d1 else 'ПРОВАЛ'}")
print(f"P-V1d2 (полосы): {bands} -> {'✓' if pv1d2 else ('ПРОВАЛ' if pv1d2_kill else 'частично')}")
print(f"P-V1d3 (fires V2000 {f2}/5, контроли чисты={not ctl_bad}): {'✓' if pv1d3 else ('ПРОВАЛ' if pv1d3_kill else 'не уст.')}")
print(f"[{time.time()-t0:.0f}s]")
