"""PRE-006 — post-hoc route classification from a single drift record. Per PREREG (frozen 2026-08-26).
Order enforced: calibration -> freeze thresholds (JSON) -> generate test -> classify."""
import json, os, sys, time
import numpy as np

# reuse PRE-004 simulators and constants verbatim
src = open("/home/claude/pre004_run.py").read()
exec(src.split("ck = json.load")[0])

CAL_JSON = "/home/claude/pre006_thresholds.json"
RES_JSON = "/home/claude/pre006_results.json"
OFF = {"fold": 0, "trans": 100, "hopf": 200}
E_N = 1500
WJ, SJ = 100, 20
WR, SR, LAGR = 500, 100, 5
RNGSH = np.random.default_rng(424242)

def sigma_E(x):
    e = x[:E_N]
    t = np.arange(E_N)
    res = e - np.polyval(np.polyfit(t, e, 1), t)
    return 1.4826 * np.median(np.abs(res - np.median(res))) + 1e-12

def feat_J(x, sE):
    best = 0.0
    for t in range(WJ, len(x) - WJ + 1, SJ):
        d = abs(np.median(x[t:t + WJ]) - np.median(x[t - WJ:t]))
        best = max(best, d)
    return best / sE

def _runs_const(sym):
    idx = np.flatnonzero(sym)
    if idx.size == 0: return np.array([1])
    if idx.size == 1: return np.array([1])
    adj = (np.diff(idx) == 1) & (sym[idx[1:]] == sym[idx[:-1]])
    bounds = np.r_[0, np.flatnonzero(~adj) + 1, idx.size]
    return np.diff(bounds)

def feat_R(x):
    """Battery O1' internal: median const-sign dphi run vs per-window shuffle floor; 2 consecutive."""
    hits = []
    for s0 in range(0, len(x) - WR + 1, SR):
        seg = x[s0:s0 + WR].astype(float)
        t = np.arange(WR)
        res = seg - np.polyval(np.polyfit(t, seg, 1), t)
        u = res[LAGR:]; v = res[:-LAGR]
        phi = np.arctan2(v, u)
        dphi = np.angle(np.exp(1j * np.diff(phi)))
        sym = np.sign(dphi).astype(np.int8)
        med = float(np.median(_runs_const(sym)))
        sh = sym.copy(); RNGSH.shuffle(sh)
        Lstar = max(8.0, 2.5 * float(_runs_const(sh).max()))
        hits.append(med >= Lstar)
    return any(hits[j] and hits[j + 1] for j in range(len(hits) - 1))

def feat_rise(x, sE):
    return (np.median(x[-500:]) - np.median(x[:E_N])) / sE

def features(x):
    sE = sigma_E(x)
    return dict(J=float(feat_J(x, sE)), R=bool(feat_R(x)), rise=float(feat_rise(x, sE)), sE=float(sE))

def classify(f, thJ, thR_alive, thRise, J_alive):
    if J_alive and f["J"] >= thJ: return "fold"
    if thR_alive and f["R"]: return "hopf"
    if f["rise"] >= thRise: return "trans"
    return "none"

def gen(name, drifting, seed):
    S = SYS[name]
    p0, p1 = S["p0"], S["p1"]
    par = (lambda t: p0 + (p1 - p0) * min(t / T_TOT, 1.0)) if drifting else (lambda t: p0)
    return S["sim"](par, seed, 1)[0]

t0 = time.time()
# ---------- Phase 1: calibration ----------
if not os.path.exists(CAL_JSON):
    cal = {n: [] for n in SYS}; ctl = []
    for name in SYS:
        for i in (1, 2, 3):
            f = features(gen(name, True, 800000 + OFF[name] + i))
            cal[name].append(f)
            print(f"калибр {name}#{i}: J={f['J']:.2f} R={f['R']} rise={f['rise']:.2f} [{time.time()-t0:.0f}s]", flush=True)
        for i in (1, 2, 3):
            f = features(gen(name, False, 810000 + OFF[name] + i))
            ctl.append(f)
            print(f"калибр-контроль {name}#{i}: J={f['J']:.2f} R={f['R']} rise={f['rise']:.2f} [{time.time()-t0:.0f}s]", flush=True)
    minJf = min(f["J"] for f in cal["fold"])
    maxJo = max(f["J"] for f in cal["trans"] + cal["hopf"])
    J_alive = minJf > maxJo
    thJ = float(np.sqrt(minJf * maxJo)) if J_alive else None
    R_alive = all(f["R"] for f in cal["hopf"]) and not any(f["R"] for f in cal["fold"] + cal["trans"])
    thRise = 2.5 * max(f["rise"] for f in ctl)
    th = dict(thJ=thJ, J_alive=bool(J_alive), minJ_fold=minJf, maxJ_other=maxJo,
              R_alive=bool(R_alive), thRise=float(thRise),
              cal={n: cal[n] for n in cal}, ctl=ctl)
    json.dump(th, open(CAL_JSON, "w"), default=float)
    print(f"\nЗАМОРОЖЕНО: J_alive={J_alive} thJ={thJ} (min_fold={minJf:.2f} / max_other={maxJo:.2f}) | "
          f"R_alive={R_alive} | thRise={thRise:.2f}", flush=True)
else:
    th = json.load(open(CAL_JSON))
    print("пороги уже заморожены:", {k: th[k] for k in ('thJ', 'J_alive', 'R_alive', 'thRise')}, flush=True)

# ---------- Phase 2: test (only after freeze) ----------
if len(sys.argv) > 1 and sys.argv[1] == "cal-only":
    sys.exit(0)
conf = {a: {b: 0 for b in ("fold", "trans", "hopf", "none")} for a in SYS}
percase = []
for name in SYS:
    for i in (1, 2, 3, 4, 5):
        f = features(gen(name, True, 900000 + OFF[name] + i))
        lab = classify(f, th["thJ"] or np.inf, th["R_alive"], th["thRise"], th["J_alive"])
        conf[name][lab] += 1
        percase.append(dict(truth=name, i=i, label=lab, **f))
        print(f"тест {name}#{i}: J={f['J']:.2f} R={f['R']} rise={f['rise']:.2f} -> {lab} [{time.time()-t0:.0f}s]", flush=True)
ctl_none = 0; ctl_cases = []
for name in SYS:
    for i in (1, 2, 3):
        f = features(gen(name, False, 910000 + OFF[name] + i))
        lab = classify(f, th["thJ"] or np.inf, th["R_alive"], th["thRise"], th["J_alive"])
        ctl_none += (lab == "none")
        ctl_cases.append(dict(truth=f"{name}-ctl", label=lab, **f))
        print(f"тест-контроль {name}#{i}: J={f['J']:.2f} R={f['R']} rise={f['rise']:.2f} -> {lab}", flush=True)

correct = sum(conf[n][n] for n in SYS)
fh_swap = conf["fold"]["hopf"] + conf["hopf"]["fold"]
pz1 = (correct >= 12) and (fh_swap == 0) and th["J_alive"]
pz1_kill = (correct <= 10) or (fh_swap >= 2) or (not th["J_alive"])
pz2 = ctl_none >= 7; pz2_kill = ctl_none <= 5
r_hopf = sum(1 for c in percase if c["truth"] == "hopf" and c["R"])
j_on_trans = sum(1 for c in percase if c["truth"] == "trans" and th["J_alive"] and c["J"] >= (th["thJ"] or np.inf))
# LOO over 15 test records for P-Z1
loo_ok = True
for k in range(len(percase)):
    sub = [c for j, c in enumerate(percase) if j != k]
    corr = sum(1 for c in sub if c["label"] == c["truth"])
    swap = sum(1 for c in sub if (c["truth"], c["label"]) in (("fold", "hopf"), ("hopf", "fold")))
    loo_ok &= (corr >= 11 and swap == 0)
out = dict(thresholds=th, confusion=conf, percase=percase, ctl_cases=ctl_cases, ctl_none=ctl_none,
           verdicts=dict(correct=correct, fh_swap=fh_swap, PZ1=bool(pz1), PZ1_killed=bool(pz1_kill),
                         PZ2=bool(pz2), PZ2_killed=bool(pz2_kill), R_hopf=r_hopf,
                         J_fold_on_trans=j_on_trans, loo_ok=bool(loo_ok)))
json.dump(out, open(RES_JSON, "w"), default=float)
print(f"\nМатрица (истина -> метки): " + " | ".join(
    f"{n}: " + ",".join(f"{b}={conf[n][b]}" for b in conf[n] if conf[n][b]) for n in SYS))
print(f"P-Z1: верных {correct}/15, фолд<->Хопф {fh_swap} -> "
      f"{'ПОДТВЕРЖДЁН' if pz1 else ('УБИТ' if pz1_kill else 'не установлен')} (LOO={loo_ok})")
print(f"P-Z2: «нет рождения» {ctl_none}/9 -> {'ПОДТВЕРЖДЁН' if pz2 else ('УБИТ' if pz2_kill else 'не установлен')}")
print(f"P-Z3: R на Хопф-тесте {r_hopf}/5; J-меток «фолд» на транскритике {j_on_trans}/5")
print(f"[{time.time()-t0:.0f}s] -> {RES_JSON}")
