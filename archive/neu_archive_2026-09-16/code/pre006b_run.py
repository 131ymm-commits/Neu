"""PRE-006b — structural return of route classifier. Per PREREG (frozen 2026-08-26).
Same architecture: calibrate -> life-check -> freeze -> blind test (seeds untouched)."""
import json, os, sys, time
import numpy as np

src = open("/home/claude/pre004_run.py").read()
exec(src.split("ck = json.load")[0])

CAL_JSON = "/home/claude/pre006b_thresholds.json"
RES_JSON = "/home/claude/pre006b_results.json"
OFF = {"fold": 0, "trans": 100, "hopf": 200}
E_N = 1500
WJ, SJ = 100, 20
WR, SR, LAGR = 500, 100, 5
TH_RISE = json.load(open("/home/claude/pre006_thresholds.json"))["thRise"]   # frozen 3.62

def feat_J2(x):
    ds = []
    for t in range(WJ, len(x) - WJ + 1, SJ):
        ds.append(abs(np.median(x[t:t + WJ]) - np.median(x[t - WJ:t])))
    ds = np.array(ds)
    return float(ds.max() / (np.percentile(ds, 90) + 1e-12))

def feat_R2(x):
    zs = []
    for s0 in range(0, len(x) - WR + 1, SR):
        seg = x[s0:s0 + WR].astype(float)
        t = np.arange(WR)
        res = seg - np.polyval(np.polyfit(t, seg, 1), t)
        u = res[LAGR:]; v = res[:-LAGR]
        phi = np.arctan2(v, u)
        dphi = np.angle(np.exp(1j * np.diff(phi)))
        sd = dphi.std() + 1e-12
        zs.append(abs(dphi.sum()) / (sd * np.sqrt(dphi.size)))
    return float(max(min(zs[j], zs[j + 1]) for j in range(len(zs) - 1)))

def feat_rise(x):
    e = x[:E_N]
    t = np.arange(E_N)
    res = e - np.polyval(np.polyfit(t, e, 1), t)
    sE = 1.4826 * np.median(np.abs(res - np.median(res))) + 1e-12
    return float((np.median(x[-500:]) - np.median(e)) / sE)

def features(x):
    return dict(J2=feat_J2(x), R2=feat_R2(x), rise=feat_rise(x))

def gen(name, drifting, seed):
    S = SYS[name]
    p0, p1 = S["p0"], S["p1"]
    par = (lambda t: p0 + (p1 - p0) * min(t / T_TOT, 1.0)) if drifting else (lambda t: p0)
    return S["sim"](par, seed, 1)[0]

t0 = time.time()
if not os.path.exists(CAL_JSON):
    cal = {n: [] for n in SYS}
    for name in SYS:
        for i in (1, 2, 3):
            f = features(gen(name, True, 800000 + OFF[name] + i))
            cal[name].append(f)
            print(f"калибр {name}#{i}: J2={f['J2']:.2f} R2={f['R2']:.2f} rise={f['rise']:.2f} [{time.time()-t0:.0f}s]", flush=True)
    minJf = min(f["J2"] for f in cal["fold"]); maxJo = max(f["J2"] for f in cal["trans"] + cal["hopf"])
    J_alive = minJf > maxJo
    thJ = float(np.sqrt(minJf * maxJo)) if J_alive else None
    minRh = min(f["R2"] for f in cal["hopf"]); maxRo = max(f["R2"] for f in cal["fold"] + cal["trans"])
    R_alive = minRh > maxRo
    thR = float(np.sqrt(minRh * maxRo)) if R_alive else None
    th = dict(thJ=thJ, J_alive=bool(J_alive), minJ_fold=minJf, maxJ_other=maxJo,
              thR=thR, R_alive=bool(R_alive), minR_hopf=minRh, maxR_other=maxRo,
              thRise=TH_RISE, cal=cal)
    json.dump(th, open(CAL_JSON, "w"), default=float)
    print(f"\nЗАМОРОЖЕНО: J_alive={J_alive} thJ={thJ} ({minJf:.2f}/{maxJo:.2f}) | "
          f"R_alive={R_alive} thR={thR} ({minRh:.2f}/{maxRo:.2f}) | thRise={TH_RISE:.2f}", flush=True)
else:
    th = json.load(open(CAL_JSON))
    print("пороги уже заморожены:", {k: th[k] for k in ('thJ', 'J_alive', 'thR', 'R_alive', 'thRise')}, flush=True)

if len(sys.argv) > 1 and sys.argv[1] == "cal-only":
    sys.exit(0)
if not (th["J_alive"] or th["R_alive"]):
    print("ОБЕ ножки мертвы — по предрегистрации P-Z1b убит; тест не вскрывается.")
    sys.exit(0)

def classify(f):
    if th["J_alive"] and f["J2"] >= th["thJ"]: return "fold"
    if th["R_alive"] and f["R2"] >= th["thR"]: return "hopf"
    if f["rise"] >= th["thRise"]: return "trans"
    return "none"

conf = {a: {b: 0 for b in ("fold", "trans", "hopf", "none")} for a in SYS}
percase = []
for name in SYS:
    for i in (1, 2, 3, 4, 5):
        f = features(gen(name, True, 900000 + OFF[name] + i))
        lab = classify(f)
        conf[name][lab] += 1
        percase.append(dict(truth=name, i=i, label=lab, **f))
        print(f"тест {name}#{i}: J2={f['J2']:.2f} R2={f['R2']:.2f} rise={f['rise']:.2f} -> {lab} [{time.time()-t0:.0f}s]", flush=True)
ctl_none = 0; ctl_cases = []
for name in SYS:
    for i in (1, 2, 3):
        f = features(gen(name, False, 910000 + OFF[name] + i))
        lab = classify(f)
        ctl_none += (lab == "none")
        ctl_cases.append(dict(truth=f"{name}-ctl", label=lab, **f))
        print(f"тест-контроль {name}#{i}: J2={f['J2']:.2f} R2={f['R2']:.2f} rise={f['rise']:.2f} -> {lab}", flush=True)

correct = sum(conf[n][n] for n in SYS)
fh_swap = conf["fold"]["hopf"] + conf["hopf"]["fold"]
pz1 = (correct >= 12) and (fh_swap == 0)
pz1_kill = (correct <= 10) or (fh_swap >= 2)
pz2 = ctl_none >= 7; pz2_kill = ctl_none <= 5
r_hopf = sum(1 for c in percase if c["truth"] == "hopf" and th["R_alive"] and c["R2"] >= th["thR"])
j_on_trans = sum(1 for c in percase if c["truth"] == "trans" and th["J_alive"] and c["J2"] >= th["thJ"])
loo_ok = True
for k in range(len(percase)):
    sub = [c for j, c in enumerate(percase) if j != k]
    corr = sum(1 for c in sub if c["label"] == c["truth"])
    swap = sum(1 for c in sub if (c["truth"], c["label"]) in (("fold", "hopf"), ("hopf", "fold")))
    loo_ok &= (corr >= 11 and swap == 0)
out = dict(thresholds=th, confusion=conf, percase=percase, ctl_cases=ctl_cases, ctl_none=ctl_none,
           verdicts=dict(correct=correct, fh_swap=fh_swap, PZ1b=bool(pz1), PZ1b_killed=bool(pz1_kill),
                         PZ2b=bool(pz2), PZ2b_killed=bool(pz2_kill), R_hopf=r_hopf,
                         J_fold_on_trans=j_on_trans, loo_ok=bool(loo_ok)))
json.dump(out, open(RES_JSON, "w"), default=float)
print(f"\nМатрица: " + " | ".join(
    f"{n}: " + ",".join(f"{b}={conf[n][b]}" for b in conf[n] if conf[n][b]) for n in SYS))
print(f"P-Z1b: верных {correct}/15, фолд<->Хопф {fh_swap} -> "
      f"{'ПОДТВЕРЖДЁН' if pz1 else ('УБИТ' if pz1_kill else 'не установлен')} (LOO={loo_ok})")
print(f"P-Z2b: «нет рождения» {ctl_none}/9 -> {'ПОДТВЕРЖДЁН' if pz2 else ('УБИТ' if pz2_kill else 'не установлен')}")
print(f"P-Z3b: R2 на Хопф-тесте {r_hopf}/5; J2-меток «фолд» на транскритике {j_on_trans}/5")
print(f"[{time.time()-t0:.0f}s] -> {RES_JSON}")
