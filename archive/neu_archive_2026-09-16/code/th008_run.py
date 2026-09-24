"""TH-008 — clocks of birth vs death in one system. Per PREREG (frozen 2026-09-02)."""
import json, time
import numpy as np
h = {}
exec(open("/home/claude/pre005b_run.py").read().split("ck = json.load")[0], h)     # sim_ext, drift, REC_DT
u = {}
exec(open("/home/claude/uni07_run.py").read().split("# ---------- root sanity")[0], u)  # sim_rev, rev, T_REV
sim_ext, drift, REC_DT = h["sim_ext"], h["drift"], h["REC_DT"]
sim_rev, rev, T_REV = u["sim_rev"], u["rev"], u["T_REV"]
t0 = time.time(); res = {}
for V in (200, 2000):
    fw = sim_ext(drift, 20290854 + V + 154, 8, V)
    w_f = []
    for r in range(8):
        c = np.flatnonzero(fw[r] > 2.2)
        if c.size: w_f.append(float(drift(c[0] * REC_DT)) - 0.30)
    bw = sim_rev(rev, 20290854 + V + 254, 8, V, T_REV)
    w_b = []
    for r in range(8):
        c = np.flatnonzero(bw[r] < 2.2)
        if c.size: w_b.append(1.10 - float(rev(c[0] * REC_DT)))
    cvf = float(np.std(w_f) / np.mean(w_f)) if len(w_f) >= 5 else None
    cvb = float(np.std(w_b) / np.mean(w_b)) if len(w_b) >= 5 else None
    jk = None
    if cvf and cvb and V == 200:
        ok = 0; tot = 0
        for i in range(len(w_b)):
            tot += 1; ok += (np.std(np.delete(w_b, i)) / np.mean(np.delete(w_b, i))) >= 3 * cvf
        jk = f"{ok}/{tot}"
    res[str(V)] = dict(w_fwd=w_f, w_back=w_b, cv_fwd=cvf, cv_back=cvb, jk=jk)
    print(f"V={V}: вперёд w={[round(x,3) for x in w_f]} CV={None if cvf is None else round(cvf,3)} | "
          f"назад w={[round(x,3) for x in w_b]} CV={None if cvb is None else round(cvb,3)} | джекнайф {jk} [{time.time()-t0:.0f}s]", flush=True)
c2 = res["200"]; c20 = res["2000"]
pt8a = c2["cv_fwd"] is not None and c2["cv_back"] is not None and c2["cv_back"] >= 3 * c2["cv_fwd"]
pt8a_kill = c2["cv_fwd"] is not None and c2["cv_back"] is not None and c2["cv_back"] <= c2["cv_fwd"]
pt8b = c20["cv_fwd"] is not None and c20["cv_back"] is not None and c20["cv_fwd"] <= 0.05 and c20["cv_back"] <= 0.05
pt8b_kill = any(q is not None and q >= 0.15 for q in (c20["cv_fwd"], c20["cv_back"]))
print(f"P-T8a (V=200: CV_назад ≥ 3×CV_вперёд): {'ПОДТВЕРЖДЁН' if pt8a else ('УБИТ' if pt8a_kill else 'не установлен')}")
print(f"P-T8b (V=2000: оба ≤ 0.05): {'ПОДТВЕРЖДЁН' if pt8b else ('УБИТ' if pt8b_kill else 'не установлен')}")
json.dump(dict(res=res, PT8a=bool(pt8a), PT8a_killed=bool(pt8a_kill), PT8b=bool(pt8b), PT8b_killed=bool(pt8b_kill)),
          open("/home/claude/th008_results.json", "w"), default=float)
print("-> th008_results.json")
