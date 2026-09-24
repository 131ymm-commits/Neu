"""PRE-008 — finish the B-edge: (A) V=2000 curve point; (B) Fano knife at V=200. Per PREREG (frozen 2026-08-26)."""
import json, os, sys, time
import numpy as np

src = open("/home/claude/pre005b_run.py").read()
exec(src.split("ck = json.load")[0])   # sim_ext, indicators, first_fire, drift/const, constants (SEED=20260854)

CKPT = "/home/claude/pre008_ckpt.json"
ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
t0 = time.time()
arg = sys.argv[1] if len(sys.argv) > 1 else "all"

# ---------- Part A: V=2000 ----------
if "V2000" not in ck and arg in ("all", "A"):
    SEED_A = 20260855
    V = 2000
    base = sim_ext(const, SEED_A + V, 5, V)
    ctrl = sim_ext(const, SEED_A + V + 77, 5, V)
    drf = sim_ext(drift, SEED_A + V + 154, 5, V)
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
    ck["V2000"] = dict(floor_var=fv, floor_ac=fa, fires=fires, leads=leads, trans_fr=trans_fr, ctrl=cf)
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"V=2000: переходы при fr={[(round(x,3) if x else None) for x in trans_fr]} | "
          f"до-пороговых {fires}/5 (lead={[round(l,3) for l in leads]}) | контроль {cf}/5 "
          f"[{time.time()-t0:.0f}s]", flush=True)

# ---------- Part B: Fano at V=200 (same seeds as PRE-005b) ----------
def indicators_fano(traj, V):
    out = []
    for s0 in range(0, NSAMP - W + 1, STRIDE):
        seg = traj[s0:s0 + W] * V          # counts
        x = np.arange(W)
        res = seg - np.polyval(np.polyfit(x, seg, 1), x)
        f = float(res.var() / max(seg.mean(), 1e-9))
        r0 = res[:-LAG]; r1 = res[LAG:]
        ac = float(np.corrcoef(r0, r1)[0, 1]) if res.std() > 0 else 0.0
        out.append((s0 + W // 2, f, ac))
    return out

if "fano200" not in ck and arg in ("all", "B"):
    V = 200
    base = sim_ext(const, SEED + V, 5, V)          # SEED=20260854 from pre005b
    ctrl = sim_ext(const, SEED + V + 77, 5, V)
    drf = sim_ext(drift, SEED + V + 154, 5, V)
    allf, alla = [], []
    for r in range(5):
        for (_, f, a) in indicators_fano(base[r], V):
            allf.append(f); alla.append(a)
    ff = 2.5 * float(np.percentile(allf, 99))
    fa = min(2.5 * float(np.percentile(alla, 99)), 0.999)
    fires, leads = 0, []
    for r in range(5):
        w_, c = first_fire(indicators_fano(drf[r], V), ff, fa)
        if c is not None and drift(c * REC_DT) < THR:
            fires += 1
            leads.append(float(THR - drift(c * REC_DT)))
    cf = sum(1 for r in range(5) if first_fire(indicators_fano(ctrl[r], V), ff, fa)[1] is not None)
    ck["fano200"] = dict(floor_f=ff, floor_ac=fa, fires=fires, leads=leads, ctrl=cf,
                         base_f_med=float(np.median(allf)))
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"Фано V=200: пол F={ff:.2f} (базовая медиана {np.median(allf):.2f}) | до-пороговых {fires}/5 "
          f"(lead={[round(l,3) for l in leads]}) | контроль {cf}/5 [{time.time()-t0:.0f}s]", flush=True)

# ---------- verdicts ----------
if "V2000" in ck and "fano200" in ck:
    tf = [x for x in ck["V2000"]["trans_fr"] if x is not None]
    n1 = sum(1 for x in tf if x >= 0.9)
    pc1 = n1 >= 4; pc1_kill = n1 <= 2
    f2 = ck["V2000"]["fires"]
    pc2 = f2 >= 4; pc2_kill = f2 <= 2
    med = float(np.median(tf)) if tf else None
    pc3 = med is not None and med >= 0.85
    pc3_kill = med is not None and med < 0.80
    pc4 = ck["V2000"]["ctrl"] <= 1 and ck["fano200"]["ctrl"] <= 1
    fb = ck["fano200"]["fires"]
    pc5 = "a" if fb >= 4 else ("b" if fb <= 1 else "не установлен")
    ck["verdicts"] = dict(n_ge09=n1, PC1=bool(pc1), PC1_killed=bool(pc1_kill),
                          PC2=bool(pc2), PC2_killed=bool(pc2_kill), med_trans=med,
                          PC3=bool(pc3), PC3_killed=bool(pc3_kill), PC4=bool(pc4), PC5=pc5)
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"\nP-C1 (fr>=0.9 при V=2000): {n1}/5 -> {'ПОДТВЕРЖДЁН' if pc1 else ('УБИТ' if pc1_kill else 'не установлен')}")
    print(f"P-C2 (предупреждение V=2000): {f2}/5 -> {'ПОДТВЕРЖДЁН' if pc2 else ('УБИТ' if pc2_kill else 'не установлен')}")
    print(f"P-C3 (кривая миграции: медиана {med}): {'ПОДТВЕРЖДЁН' if pc3 else ('УБИТ' if pc3_kill else 'не установлен')} (0.38 / 0.85 / {med})")
    print(f"P-C4 (контроли): {'ПОДТВЕРЖДЁН' if pc4 else 'УБИТ'}")
    print(f"P-C5 (Фано-механизм V=200): {ck['fano200']['fires']}/5 -> ветвь ({pc5})")
print(f"[{time.time()-t0:.0f}s]")
