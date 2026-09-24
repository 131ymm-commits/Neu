"""PRE-010 — oscillator leg v2: A-gate (amplitude) + T-gate (full turns). Per PREREG (frozen 2026-08-31)."""
import json, os, time
import numpy as np

exec(open("/home/claude/pre006c_run.py").read().split("t0 = time.time()")[0])   # SYS, gen, feats machinery, OFF
th = json.load(open("/home/claude/pre006c_thresholds.json"))
CK = "/home/claude/pre010_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()

def leg_stats(x):
    """Per sliding window: z_j, RMS_j, T_j; return R2 (as before), winning-pair A and Tw."""
    zs, rms, turns = [], [], []
    for s0 in range(0, len(x) - WR + 1, SR):
        seg = x[s0:s0 + WR].astype(float)
        t = np.arange(WR)
        res = seg - np.polyval(np.polyfit(t, seg, 1), t)
        u = res[LAGR:]; v = res[:-LAGR]
        phi = np.arctan2(v, u)
        dphi = np.angle(np.exp(1j * np.diff(phi)))
        sd = dphi.std() + 1e-12
        zs.append(abs(dphi.sum()) / (sd * np.sqrt(dphi.size)))
        rms.append(float(np.sqrt(np.mean(res ** 2))))
        turns.append(float(abs(dphi.sum()) / (2 * np.pi)))
    pair = [min(zs[j], zs[j + 1]) for j in range(len(zs) - 1)]
    jstar = int(np.argmax(pair))
    R2 = float(pair[jstar])
    _, medE = feat_rise_sE(x)
    e = x[:E_N]; t = np.arange(E_N)
    res_e = e - np.polyval(np.polyfit(t, e, 1), t)
    sE = 1.4826 * np.median(np.abs(res_e - np.median(res_e))) + 1e-12
    A = float(min(rms[jstar], rms[jstar + 1]) / sE)
    Tw = float(min(turns[jstar], turns[jstar + 1]))
    return R2, A, Tw

TH_T = 2.0

# ---------- calibration of th_A on NEW seeds ----------
if "cal" not in ck:
    true_A, ctl_A = [], []
    for i in (1, 2, 3):
        x = gen("hopf", True, 980200 + i)
        R2, A, Tw = leg_stats(x)
        true_A.append(A)
        print(f"калибр hopf-дрейф#{i}: R2={R2:.1f} A={A:.2f} T={Tw:.1f} [{time.time()-t0:.0f}s]", flush=True)
    for i in (1, 2, 3):
        x = gen("hopf", False, 985200 + i)
        R2, A, Tw = leg_stats(x)
        ctl_A.append(A)
        print(f"калибр hopf-безд#{i}: R2={R2:.1f} A={A:.2f} T={Tw:.1f} [{time.time()-t0:.0f}s]", flush=True)
    alive = min(true_A) > max(ctl_A)
    thA = float(np.sqrt(min(true_A) * max(ctl_A))) if alive else None
    ck["cal"] = dict(true_A=true_A, ctl_A=ctl_A, alive=bool(alive), thA=thA)
    json.dump(ck, open(CK, "w"), default=float)
    print(f"ЗАМОРОЖЕНО: A-гейт alive={alive}, th_A={thA} (min_true={min(true_A):.2f} / max_ctl={max(ctl_A):.2f})", flush=True)
if not ck["cal"]["alive"]:
    print("A-гейт мёртв на калибровке (перекрытие) — по предрегистрации стоп с записью.")
    raise SystemExit
TH_A = ck["cal"]["thA"]

def classify_v2(x):
    R2, A, Tw = leg_stats(x)
    f_rise, _ = feat_rise_sE(x)
    S = feat_S(x)
    if R2 >= th["thR2"] and A >= TH_A and Tw >= TH_T:
        lab = "hopf"
    elif f_rise < th["thRise"]:
        lab = "none"
    elif S is not None and S >= th["thS"]:
        lab = "fold"
    else:
        lab = "trans"
    return lab, dict(R2=R2, A=A, Tw=Tw, rise=f_rise, S=S)

# ---------- v2 on untouched ver001c sets ----------
if "test" not in ck:
    percase, ctl = [], []
    for name in SYS:
        for i in (1, 2, 3, 4, 5):
            lab, f = classify_v2(gen(name, True, 970000 + OFF[name] + i))
            percase.append(dict(truth=name, i=i, label=lab, **f))
            print(f"v2 тест {name}#{i}: R2={f['R2']:.1f} A={f['A']:.2f} T={f['Tw']:.1f} -> {lab} [{time.time()-t0:.0f}s]", flush=True)
    for name in SYS:
        for i in (1, 2, 3):
            lab, f = classify_v2(gen(name, False, 975000 + OFF[name] + i))
            ctl.append(dict(truth=name, i=i, label=lab, **f))
            print(f"v2 контроль {name}#{i}: R2={f['R2']:.1f} A={f['A']:.2f} T={f['Tw']:.1f} -> {lab} [{time.time()-t0:.0f}s]", flush=True)
    ck["test"] = dict(percase=percase, ctl=ctl)
    json.dump(ck, open(CK, "w"), default=float)

pc, cc = ck["test"]["percase"], ck["test"]["ctl"]
hopf_ok = sum(1 for c in pc if c["truth"] == "hopf" and c["label"] == "hopf")
correct = sum(1 for c in pc if c["label"] == c["truth"])
fh = sum(1 for c in pc if (c["truth"], c["label"]) in (("fold", "hopf"), ("hopf", "fold")))
hctl_none = sum(1 for c in cc if c["truth"] == "hopf" and c["label"] == "none")
ctl_none = sum(1 for c in cc if c["label"] == "none")
loo_ok = all(sum(1 for j, c in enumerate(pc) if j != k and c["label"] == c["truth"]) >= 11 for k in range(len(pc)))
p1 = hopf_ok >= 4 and correct >= 12 and fh == 0
p1_kill = hopf_ok <= 2
p2 = hctl_none >= 2 and ctl_none >= 7
p2_kill = ctl_none <= 5
ck["verdicts"] = dict(hopf_ok=hopf_ok, correct=correct, fh=fh, hctl_none=hctl_none, ctl_none=ctl_none,
                      PP10a1=bool(p1), PP10a1_killed=bool(p1_kill), PP10a2=bool(p2), PP10a2_killed=bool(p2_kill),
                      loo_ok=bool(loo_ok))
json.dump(ck, open(CK, "w"), default=float)
print(f"\nP-P10a1: hopf-тесты {hopf_ok}/5, верных {correct}/15, ф↔Х {fh} -> "
      f"{'ПОДТВЕРЖДЁН' if p1 else ('УБИТ' if p1_kill else 'не установлен')} (LOO={loo_ok})")
print(f"P-P10a2: hopf-контроли none {hctl_none}/3, все контроли {ctl_none}/9 (v1 было 6/9) -> "
      f"{'ПОДТВЕРЖДЁН' if p2 else ('УБИТ' if p2_kill else 'не установлен')}")
print(f"[{time.time()-t0:.0f}s] -> {CK}")
