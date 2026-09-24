"""PRE-006c — C1-transient leg in the route classifier. Per PREREG (frozen 2026-08-26).
Fresh test seeds 920000/930000; R2 and rise thresholds inherited frozen."""
import json, os, sys, time
import numpy as np

src = open("/home/claude/pre004_run.py").read()
exec(src.split("ck = json.load")[0])

CAL_JSON = "/home/claude/pre006c_thresholds.json"
RES_JSON = "/home/claude/pre006c_results.json"
OFF = {"fold": 0, "trans": 100, "hopf": 200}
E_N = 1500
WR, SR, LAGR = 500, 100, 5
TH_R2 = json.load(open("/home/claude/pre006b_thresholds.json"))["thR"]      # 9.5667 frozen
TH_RISE = json.load(open("/home/claude/pre006_thresholds.json"))["thRise"]  # 3.6167 frozen

def medfilt(x, k=51):
    from scipy.ndimage import median_filter
    return median_filter(x.astype(float), size=k, mode="nearest")

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

def feat_rise_sE(x):
    e = x[:E_N]
    t = np.arange(E_N)
    res = e - np.polyval(np.polyfit(t, e, 1), t)
    sE = 1.4826 * np.median(np.abs(res - np.median(res))) + 1e-12
    return float((np.median(x[-500:]) - np.median(e)) / sE), float(np.median(e))

def feat_S(x):
    """C1 ratio: t_wait / t_cross via 20%/80% levels on median-filtered record."""
    rise_sig, medE = feat_rise_sE(x)
    late = float(np.median(x[-500:]))
    L20 = medE + 0.2 * (late - medE)
    L80 = medE + 0.8 * (late - medE)
    xm = medfilt(x)
    hi = np.flatnonzero(xm >= L80)
    if hi.size == 0: return None
    h0 = hi[0]
    lo = np.flatnonzero(xm[:h0] <= L20)
    if lo.size == 0: return None
    d0 = lo[-1]
    t_wait = d0 * REC_DT
    t_cross = (h0 - d0) * REC_DT
    if t_cross <= 0: return None
    return float(t_wait / t_cross)

def features(x):
    rise, _ = feat_rise_sE(x)
    return dict(R2=feat_R2(x), rise=rise, S=feat_S(x))

def gen(name, drifting, seed):
    S_ = SYS[name]
    p0, p1 = S_["p0"], S_["p1"]
    par = (lambda t: p0 + (p1 - p0) * min(t / T_TOT, 1.0)) if drifting else (lambda t: p0)
    return S_["sim"](par, seed, 1)[0]

t0 = time.time()
if not os.path.exists(CAL_JSON):
    calS = {"fold": [], "trans": []}
    for name in ("fold", "trans"):
        for i in (1, 2, 3):
            x = gen(name, True, 800000 + OFF[name] + i)
            s = feat_S(x)
            calS[name].append(s)
            print(f"калибр {name}#{i}: S={s if s is None else round(s,2)} [{time.time()-t0:.0f}s]", flush=True)
    ok = all(s is not None for s in calS["fold"] + calS["trans"])
    if ok:
        minSf = min(calS["fold"]); maxSt = max(calS["trans"])
        S_alive = minSf > maxSt
        thS = float(np.sqrt(minSf * maxSt)) if S_alive else None
    else:
        S_alive, thS, minSf, maxSt = False, None, None, None
    th = dict(thS=thS, S_alive=bool(S_alive), minS_fold=minSf, maxS_trans=maxSt, cal=calS,
              thR2=TH_R2, thRise=TH_RISE)
    json.dump(th, open(CAL_JSON, "w"), default=float)
    print(f"\nЗАМОРОЖЕНО: S_alive={S_alive} thS={thS} ({minSf}/{maxSt}) | thR2={TH_R2:.2f} | thRise={TH_RISE:.2f}", flush=True)
else:
    th = json.load(open(CAL_JSON))
    print("пороги уже заморожены:", {k: th[k] for k in ('thS', 'S_alive', 'thR2', 'thRise')}, flush=True)

if len(sys.argv) > 1 and sys.argv[1] == "cal-only":
    sys.exit(0)
if not th["S_alive"]:
    print("S-ножка мертва на калибровке — по предрегистрации P-Z1c убит; тест не вскрывается.")
    sys.exit(0)

def classify(f):
    if f["R2"] >= th["thR2"]: return "hopf"
    if f["rise"] < th["thRise"]: return "none"
    if f["S"] is not None and f["S"] >= th["thS"]: return "fold"
    return "trans"

conf = {a: {b: 0 for b in ("fold", "trans", "hopf", "none")} for a in SYS}
percase = []
for name in SYS:
    for i in (1, 2, 3, 4, 5):
        f = features(gen(name, True, 920000 + OFF[name] + i))
        lab = classify(f)
        conf[name][lab] += 1
        percase.append(dict(truth=name, i=i, label=lab, **f))
        print(f"тест {name}#{i}: R2={f['R2']:.2f} rise={f['rise']:.2f} S={f['S'] if f['S'] is None else round(f['S'],2)} -> {lab} [{time.time()-t0:.0f}s]", flush=True)
ctl_none = 0; ctl_cases = []
for name in SYS:
    for i in (1, 2, 3):
        f = features(gen(name, False, 930000 + OFF[name] + i))
        lab = classify(f)
        ctl_none += (lab == "none")
        ctl_cases.append(dict(truth=f"{name}-ctl", label=lab, **f))
        print(f"тест-контроль {name}#{i}: R2={f['R2']:.2f} rise={f['rise']:.2f} -> {lab}", flush=True)

correct = sum(conf[n][n] for n in SYS)
fh_swap = conf["fold"]["hopf"] + conf["hopf"]["fold"]
pz1 = (correct >= 12) and (fh_swap == 0)
pz1_kill = (correct <= 10) or (fh_swap >= 2)
pz2 = ctl_none >= 7; pz2_kill = ctl_none <= 5
s_fold = sum(1 for c in percase if c["truth"] == "fold" and c["S"] is not None and c["S"] >= th["thS"])
s_trans_below = sum(1 for c in percase if c["truth"] == "trans" and (c["S"] is None or c["S"] < th["thS"]))
loo_ok = True
for k in range(len(percase)):
    sub = [c for j, c in enumerate(percase) if j != k]
    corr = sum(1 for c in sub if c["label"] == c["truth"])
    swap = sum(1 for c in sub if (c["truth"], c["label"]) in (("fold", "hopf"), ("hopf", "fold")))
    loo_ok &= (corr >= 11 and swap == 0)
out = dict(thresholds=th, confusion=conf, percase=percase, ctl_cases=ctl_cases, ctl_none=ctl_none,
           verdicts=dict(correct=correct, fh_swap=fh_swap, PZ1c=bool(pz1), PZ1c_killed=bool(pz1_kill),
                         PZ2c=bool(pz2), PZ2c_killed=bool(pz2_kill), S_fold=s_fold,
                         S_trans_below=s_trans_below, loo_ok=bool(loo_ok)))
json.dump(out, open(RES_JSON, "w"), default=float)
print(f"\nМатрица: " + " | ".join(
    f"{n}: " + ",".join(f"{b}={conf[n][b]}" for b in conf[n] if conf[n][b]) for n in SYS))
print(f"P-Z1c: верных {correct}/15, фолд<->Хопф {fh_swap} -> "
      f"{'ПОДТВЕРЖДЁН' if pz1 else ('УБИТ' if pz1_kill else 'не установлен')} (LOO={loo_ok})")
print(f"P-Z2c: «нет рождения» {ctl_none}/9 -> {'ПОДТВЕРЖДЁН' if pz2 else ('УБИТ' if pz2_kill else 'не установлен')}")
print(f"P-Z3c: S на фолд-тесте {s_fold}/5 >= порога; транскритика ниже порога {s_trans_below}/5")
print(f"[{time.time()-t0:.0f}s] -> {RES_JSON}")
