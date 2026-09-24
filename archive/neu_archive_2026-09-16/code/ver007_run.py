"""VER-007 — analysis-constants multiverse. Per PREREG (frozen 2026-08-31).
(a) UNI-04d 27 combos; (b) migration crossing line x3; (c) tree v2 windows 9 combos."""
import json, os, time
import numpy as np

CK = "/home/claude/ver007_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()

# ============ (a) UNI-04d ============
if "a" not in ck:
    g = {}
    exec(open("/home/claude/uni04d_run.py").read().split("\nres = {}")[0], g)   # sim, wind_raw, classify, feats, TH, V
    TRAJ = {}
    for tau in (0.05, 0.40):
        TRAJ[tau] = g["sim"](tau, True, 990300 + int(tau * 100), 5)
        print(f"(а) траектории τ={tau} готовы [{time.time()-t0:.0f}s]", flush=True)

    def label_var(traj, c, B, m):
        seg = traj[-4000:]
        z, thw, fire, rms = g["wind_raw"](seg)
        xbar = max(float(np.mean(seg)), 1e-6)
        amp_ok = rms >= m * np.sqrt(xbar / g["V"])
        if fire and amp_ok: return "осциллятор"
        blocks = traj[:len(traj) // B * B].reshape(-1, B).mean(1)
        n20 = max(int(round(20 * 240 / B)), 4)      # onset-guard scaled to block size
        cr = np.flatnonzero(blocks > c)
        if cr.size and cr[0] >= n20:
            i_on = int(cr[0]); lo = max(i_on - int(80 * 240 / B), 0)
            w = blocks[lo:min(i_on + int(20 * 240 / B), len(blocks))]
            return g["classify"](g["feats"](w, i_on - lo), g["TH"])
        w = blocks[-int(100 * 240 / B):]
        return g["classify"](g["feats"](w, int(80 * 240 / B)), g["TH"])

    combos = []
    for c in (2.0, 2.2, 2.4):
        for B in (120, 240, 480):
            for m in (7.5, 10.0, 12.5):
                ok_lo = sum(1 for r in range(5) if label_var(TRAJ[0.05][r], c, B, m) == "фолд")
                ok_hi = sum(1 for r in range(5) if label_var(TRAJ[0.40][r], c, B, m) == "осциллятор")
                combos.append(dict(c=c, B=B, m=m, lo=ok_lo, hi=ok_hi, keep=bool(ok_lo >= 4 and ok_hi >= 4)))
    nkeep = sum(1 for x in combos if x["keep"])
    base = [x for x in combos if x["c"] == 2.2 and x["B"] == 240 and x["m"] == 10.0][0]
    ck["a"] = dict(combos=combos, nkeep=nkeep, base=base,
                   PV7a=bool(nkeep >= 24), PV7a_killed=bool(nkeep < 14),
                   sanity_base=bool(base["lo"] >= 4 and base["hi"] >= 4))
    json.dump(ck, open(CK, "w"), default=float)
    bad = [f"c={x['c']},B={x['B']},m={x['m']}:{x['lo']}/{x['hi']}" for x in combos if not x["keep"]]
    print(f"P-V7a: вердикт выживает в {nkeep}/27 (санити базы: {ck['a']['sanity_base']}) "
          f"-> {'✓' if ck['a']['PV7a'] else ('УБИТ' if ck['a']['PV7a_killed'] else 'не уст.')} | провалы: {bad} [{time.time()-t0:.0f}s]", flush=True)

# ============ (b) migration crossing ============
if "b" not in ck:
    h = {}
    exec(open("/home/claude/pre005b_run.py").read().split("ck = json.load")[0], h)
    meds = {}
    for V, SB in ((20, 20270854), (200, 20270854), (2000, 20270855)):
        drf = h["sim_ext"](h["drift"], SB + V + 154, 5, V)
        meds[V] = {}
        for c in (2.0, 2.2, 2.4):
            tf = []
            for r in range(5):
                cross = np.flatnonzero(drf[r] > c)
                if cross.size: tf.append(float(h["drift"](cross[0] * h["REC_DT"])))
            meds[V][c] = float(np.median(tf)) if tf else None
        print(f"(б) V={V}: медианы по c = {meds[V]} [{time.time()-t0:.0f}s]", flush=True)
    mono = {c: (meds[20][c] is not None and meds[200][c] is not None and meds[2000][c] is not None
                and meds[20][c] < meds[200][c] < meds[2000][c]) for c in (2.0, 2.2, 2.4)}
    def bands_ok(c):
        return (0.25 <= meds[20][c] <= 0.55) and (0.75 <= meds[200][c] <= 0.95) and meds[2000][c] >= 0.90
    nb = sum(1 for c in (2.0, 2.2, 2.4) if bands_ok(c))
    ck["b"] = dict(meds={str(V): {str(c): meds[V][c] for c in meds[V]} for V in meds},
                   mono=all(mono.values()), bands_c=nb,
                   PV7b=bool(all(mono.values()) and nb >= 2), PV7b_killed=bool(not all(mono.values())))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"P-V7b: монотонность при всех c: {all(mono.values())}; полосы при {nb}/3 значений c "
          f"-> {'✓' if ck['b']['PV7b'] else ('УБИТ' if ck['b']['PV7b_killed'] else 'не уст.')} [{time.time()-t0:.0f}s]", flush=True)

# ============ (c) tree v2 windows ============
if "c" not in ck:
    p = {}
    exec(open("/home/claude/pre006c_run.py").read().split("t0 = time.time()")[0], p)
    th6 = json.load(open("/home/claude/pre006c_thresholds.json"))
    thA = json.load(open("/home/claude/pre010_ckpt.json"))["cal"]["thA"]
    TRJ = {}
    for name in p["SYS"]:
        for i in (1, 2, 3, 4, 5):
            TRJ[(name, i)] = p["gen"](name, True, 970000 + p["OFF"][name] + i)
    print(f"(в) 15 траекторий готовы [{time.time()-t0:.0f}s]", flush=True)

    def leg(x, WR, EN):
        SR, LAGR = 100, 5
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
        j = int(np.argmax(pair))
        e = x[:EN]; t = np.arange(EN)
        res_e = e - np.polyval(np.polyfit(t, e, 1), t)
        sE = 1.4826 * np.median(np.abs(res_e - np.median(res_e))) + 1e-12
        eN = float(np.median(x[:EN]))
        rise = float((np.median(x[-500:]) - eN) / sE)
        return float(pair[j]), float(min(rms[j], rms[j + 1]) / sE), float(min(turns[j], turns[j + 1])), rise

    def cls(x, WR, EN):
        R2, A, Tw, rise = leg(x, WR, EN)
        if R2 >= th6["thR2"] and A >= thA and Tw >= 2.0: return "hopf"
        if rise < th6["thRise"]: return "none"
        S = p["feat_S"](x)
        if S is not None and S >= th6["thS"]: return "fold"
        return "trans"

    rows = []
    for WR in (400, 500, 600):
        for EN in (1200, 1500, 1800):
            correct = fh = 0
            for (name, i), x in TRJ.items():
                lab = cls(x, WR, EN)
                correct += (lab == name)
                fh += (name, lab) in (("fold", "hopf"), ("hopf", "fold"))
            rows.append(dict(WR=WR, EN=EN, correct=correct, fh=fh))
            print(f"(в) WR={WR} EN={EN}: верных {correct}/15, ф↔Х {fh} [{time.time()-t0:.0f}s]", flush=True)
    n_ok = sum(1 for r in rows if r["correct"] >= 12)
    fh_all0 = all(r["fh"] == 0 for r in rows)
    nbad = sum(1 for r in rows if r["correct"] <= 10)
    ck["c"] = dict(rows=rows, n_ok=n_ok, fh_all0=bool(fh_all0),
                   PV7c=bool(n_ok >= 8 and fh_all0), PV7c_killed=bool(nbad >= 3))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"P-V7c: верных ≥12/15 в {n_ok}/9 комбинаций, ф↔Х=0 во всех: {fh_all0} "
          f"-> {'✓' if ck['c']['PV7c'] else ('УБИТ' if ck['c']['PV7c_killed'] else 'не уст.')} [{time.time()-t0:.0f}s]", flush=True)

print(f"[VER-007 done {time.time()-t0:.0f}s]")
