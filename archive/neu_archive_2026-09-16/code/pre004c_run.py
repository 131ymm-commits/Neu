"""PRE-004c — fold warning vs drift rate. Per PREREG (frozen 2026-08-24)."""
import json, os, sys, time
import numpy as np

exec(open("/home/claude/pre004_run.py").read().split("ck = json.load")[0])

SEEDC = 20260852
CKPT = "/home/claude/pre004c_ckpt.json"
ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
t0 = time.time()
arg = sys.argv[1] if len(sys.argv) > 1 else "all"

S = SYS["fold"]
p0, p1, thr = S["p0"], S["p1"], S["thr"]

def run_speed(T_drift, seed):
    global T_TOT, NSAMP
    T_save, N_save = T_TOT, NSAMP
    T_TOT = T_drift
    NSAMP = int(T_drift / REC_DT)
    drift = lambda t: p0 + (p1 - p0) * min(t / T_drift, 1.0)
    const = lambda t: p0
    base = S["sim"](const, seed, 5)
    ctrl = S["sim"](const, seed + 77, 5)
    drf = S["sim"](drift, seed + 154, 5)
    fv = fa = -np.inf
    for r in range(5):
        for (_, v, a) in indicators(base[r]):
            fv = max(fv, v); fa = max(fa, a)
    fv *= 2.5; fa = min(2.5 * fa, 0.999)
    fires, leads = 0, []
    for r in range(5):
        w_, c = first_fire(indicators(drf[r]), fv, fa)
        if c is not None and drift(c * REC_DT) < thr:
            fires += 1
            leads.append(float(thr - drift(c * REC_DT)))
    cf = sum(1 for r in range(5) if first_fire(indicators(ctrl[r]), fv, fa)[1] is not None)
    T_TOT, NSAMP = T_save, N_save
    return dict(fires=fires, leads=leads, ctrl=cf, floor_var=fv)

for T_d in (600, 2400, 9600):
    key = f"T{T_d}"
    if key in ck: continue
    if arg != "all" and arg != str(T_d): continue
    ck[key] = run_speed(float(T_d), SEEDC + T_d)
    json.dump(ck, open(CKPT, "w"), default=float)
    e = ck[key]
    print(f"T_drift={T_d}: до-пороговых {e['fires']}/5 (lead fr: {[round(l,3) for l in e['leads']]}) "
          f"| контроль {e['ctrl']}/5 [{time.time()-t0:.0f}s]", flush=True)

if all(f"T{T}" in ck for T in (600, 2400, 9600)):
    f6, f24, f96 = ck["T600"]["fires"], ck["T2400"]["fires"], ck["T9600"]["fires"]
    px1 = (f6 <= f24 <= f96) and f96 >= 4
    px1_kill = f96 <= 2
    ml6 = float(np.median(ck["T600"]["leads"])) if ck["T600"]["leads"] else None
    ml96 = float(np.median(ck["T9600"]["leads"])) if ck["T9600"]["leads"] else None
    px2 = (ml6 is not None and ml96 is not None and ml96 < ml6)
    px3_bad = [T for T in (600, 2400, 9600) if ck[f"T{T}"]["ctrl"] >= 2]
    ck["verdicts"] = dict(fires=[f6, f24, f96], PX1=bool(px1), PX1_killed=bool(px1_kill),
                          ml600=ml6, ml9600=ml96, PX2=bool(px2), PX3=len(px3_bad) == 0)
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"\nP-X1: {f6}->{f24}->{f96} из 5 -> {'ПОДТВЕРЖДЁН' if px1 else ('УБИТ' if px1_kill else 'не установлен')}")
    print(f"P-X2 (lead при 9600 < при 600): {ml96} vs {ml6} -> {'подтверждён' if px2 else 'не подтверждён'}")
    print(f"P-X3 (контроли): {'ПОДТВЕРЖДЁН' if not px3_bad else 'УБИТ: ' + str(px3_bad)}")
print(f"[{time.time()-t0:.0f}s]")
