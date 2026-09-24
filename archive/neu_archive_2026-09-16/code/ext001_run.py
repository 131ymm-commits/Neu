"""EXT-001 — frozen route tree on NGRIP (first external data). Per PREREG (frozen 2026-08-26).
Phase A: calibrate+validate on coarse-grained CME (blind to NGRIP). Phase B: single blind NGRIP pass."""
import json, os, sys, time
import numpy as np
from scipy.ndimage import median_filter

src = open("/home/claude/pre004_run.py").read()
exec(src.split("ck = json.load")[0])   # sim_schlogl, sim_verhulst, SYS, T_TOT=600, REC_DT=0.1

CKPT = "/home/claude/ext001_ckpt.json"
XLS = "/root/.claude/uploads/229af6ff-ce23-5c39-8321-25610f039873/ba8cec9a-GICC05_NGRIP_60ka_20y_10sep2007_1.xls"
BLOCK = 60          # 6000 -> 100 samples
LAG_R2 = 12
ONSETS = dict([("YD/PB", 11703), ("GI-1", 14692), ("GI-2", 23340), ("GI-3", 27780),
               ("GI-4", 28900), ("GI-5", 32500), ("GI-6", 33740), ("GI-7", 35480),
               ("GI-8", 38220), ("GI-9", 40160), ("GI-10", 41460), ("GI-11", 43340),
               ("GI-12", 46860), ("GI-13", 49280), ("GI-14", 54220), ("GI-15", 55800),
               ("GI-16", 58280), ("GI-17", 59440)])
CTRL_EVENTS = ["GI-1", "GI-2", "GI-4", "GI-11", "GI-13"]

# ---------- window feature machinery (frozen scaled forms) ----------
def feats(win, i_on):
    """win: 1D array oriented with time FORWARD (transition near the end at index i_on);
    E = [0 .. i_on-5]; post = [i_on+5 .. i_on+20]."""
    N = len(win)
    E = win[:max(i_on - 5, 10)]
    post = win[i_on + 5: min(i_on + 20, N)]
    if len(post) < 5: post = win[i_on:]
    t = np.arange(len(E))
    res = E - np.polyval(np.polyfit(t, E, 1), t)
    sE = 1.4826 * np.median(np.abs(res - np.median(res))) + 1e-12
    mE, mP = float(np.median(E)), float(np.median(post))
    rise = (mP - mE) / sE
    # S leg
    xm = median_filter(win.astype(float), size=3, mode="nearest")
    L20 = mE + 0.2 * (mP - mE); L80 = mE + 0.8 * (mP - mE)
    S = None
    hi = np.flatnonzero(xm >= L80) if mP > mE else np.array([])
    if hi.size:
        h0 = hi[0]
        lo = np.flatnonzero(xm[:h0] <= L20)
        if lo.size and h0 > lo[-1]:
            S = float(lo[-1] / (h0 - lo[-1]))
    # R2 winding on the whole window
    t2 = np.arange(N)
    r2res = win - np.polyval(np.polyfit(t2, win, 1), t2)
    u = r2res[LAG_R2:]; v = r2res[:-LAG_R2]
    phi = np.arctan2(v, u)
    dphi = np.angle(np.exp(1j * np.diff(phi)))
    z = float(abs(dphi.sum()) / ((dphi.std() + 1e-12) * np.sqrt(dphi.size)))
    return dict(rise=float(rise), S=S, z=z, N=N, i_on=int(i_on))

def classify(f, th):
    if f["z"] >= th["thR2"]: return "осциллятор"
    if f["rise"] < th["thRise"]: return "нет рождения"
    if f["S"] is not None and f["S"] >= th["thS"]: return "фолд"
    return "непрерывный"

# ---------- Phase A ----------
def coarse(traj):
    n = (len(traj) // BLOCK) * BLOCK
    return traj[:n].reshape(-1, BLOCK).mean(1)

def cme_window(name, drifting, seed):
    S_ = SYS[name]
    p0, p1 = S_["p0"], S_["p1"]
    par = (lambda t: p0 + (p1 - p0) * min(t / T_TOT, 1.0)) if drifting else (lambda t: p0)
    x = coarse(S_["sim"](par, seed, 1)[0])          # 100 samples, 6 t.u. each
    if not drifting:
        i_on = 80                                    # stadial-only analog: no transition
        w = x[:100]
        return w, i_on
    if name == "fold":
        cr = np.flatnonzero(x > (x[:20].mean() + 25))  # counts midline ~ dark+25 (V=20: dark~20, hot~70)
        i_on = int(cr[0]) if cr.size else None
    else:
        i_on = 50                                    # lambda=1 at t=300 -> sample 50
    if i_on is None or i_on < 20: return None, None
    lo = max(i_on - 80, 0)
    hi = min(i_on + 20, len(x))
    return x[lo:hi], i_on - lo

t0 = time.time()
ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}

if "th" not in ck:
    Sf, St, zs = [], [], []
    for name, bag in (("fold", Sf), ("trans", St)):
        for i in (1, 2, 3):
            w, ion = cme_window(name, True, 990000 + i + (0 if name == "fold" else 100))
            if w is None: continue
            f = feats(w, ion)
            bag.append(f["S"] if f["S"] is not None else -1)
            zs.append(f["z"])
            print(f"калибр {name}#{i}: S={f['S'] if f['S'] is None else round(f['S'],2)} rise={f['rise']:.1f} z={f['z']:.2f}", flush=True)
    rises = []
    for name in ("fold", "trans"):
        for i in (1, 2, 3):
            w, ion = cme_window(name, False, 990500 + i + (0 if name == "fold" else 100))
            f = feats(w, ion)
            rises.append(f["rise"]); zs.append(f["z"])
            print(f"калибр-контроль {name}#{i}: rise={f['rise']:.2f} z={f['z']:.2f}", flush=True)
    ok = all(s > 0 for s in Sf + St)
    alive = ok and min(Sf) > max(St)
    thS = float(np.sqrt(min(Sf) * max(St))) if alive else None
    thRise = 2.5 * max(rises)
    thR2 = 2.5 * float(np.percentile(zs, 99))
    ck["th"] = dict(thS=thS, S_alive=bool(alive), minS_fold=min(Sf) if Sf else None,
                    maxS_trans=max(St) if St else None, thRise=float(thRise), thR2=float(thR2))
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"\nЗАМОРОЖЕНО: S_alive={alive} thS={thS} ({min(Sf) if Sf else None}/{max(St) if St else None}) "
          f"thRise={thRise:.2f} thR2={thR2:.2f}", flush=True)
th = ck["th"]
if not th["S_alive"]:
    print("S-ножка мертва на грубой геометрии — по предрегистрации NGRIP не вскрывается."); sys.exit(0)

if "valid" not in ck:
    correct, ctl_ok, rows = 0, 0, []
    for name, want in (("fold", "фолд"), ("trans", "непрерывный")):
        for i in (1, 2, 3, 4, 5):
            w, ion = cme_window(name, True, 991000 + i + (0 if name == "fold" else 100))
            if w is None:
                rows.append(dict(sys=name, i=i, label="окно-провал")); continue
            f = feats(w, ion)
            lab = classify(f, th)
            correct += (lab == want)
            rows.append(dict(sys=name, i=i, label=lab, **{k: f[k] for k in ("rise", "S", "z")}))
            print(f"валид {name}#{i}: S={f['S'] if f['S'] is None else round(f['S'],2)} rise={f['rise']:.1f} z={f['z']:.2f} -> {lab}", flush=True)
    for j, name in enumerate(("fold", "trans", "fold", "trans", "fold", "trans")):
        w, ion = cme_window(name, False, 991500 + j)
        f = feats(w, ion)
        lab = classify(f, th)
        ctl_ok += (lab == "нет рождения")
        print(f"валид-контроль {j}: rise={f['rise']:.2f} z={f['z']:.2f} -> {lab}", flush=True)
    pe1 = correct >= 8 and ctl_ok >= 5
    pe1_kill = correct <= 6 or ctl_ok <= 3
    ck["valid"] = dict(correct=correct, ctl_ok=ctl_ok, rows=rows, PE1=bool(pe1), PE1_killed=bool(pe1_kill))
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"\nP-E1: {correct}/10 верных, контроли {ctl_ok}/6 -> "
          f"{'ПОДТВЕРЖДЁН — NGRIP вскрывается' if pe1 else ('УБИТ — NGRIP НЕ вскрывается' if pe1_kill else 'не установлен — стоп')}", flush=True)
if not ck["valid"]["PE1"]:
    sys.exit(0)

# ---------- Phase B: single blind NGRIP pass ----------
if "ngrip" not in ck:
    import xlrd
    wb = xlrd.open_workbook(XLS); sh = wb.sheet_by_index(0)
    ages, d18 = [], []
    for r in range(61, sh.nrows):
        a, d = sh.cell_value(r, 0), sh.cell_value(r, 2)
        if isinstance(a, float) and isinstance(d, float):
            ages.append(a); d18.append(d)
    ages = np.array(ages); d18 = np.array(d18)
    order = np.argsort(-ages)                     # time forward = decreasing b2k
    ages, d18 = ages[order], d18[order]
    names = sorted(ONSETS, key=lambda k: -ONSETS[k])
    older = {}
    for i, nm in enumerate(names):
        older[nm] = 60000.0 if i == 0 else ONSETS[names[i - 1]]
    events, ctrls = [], []
    for nm in names:
        on = ONSETS[nm]
        pre = min(1600, older[nm] - 200 - on)
        if pre < 800:
            events.append(dict(name=nm, label="исключён (пре-спан<800)", pre=pre)); continue
        m = (ages <= on + pre) & (ages >= on - 400)
        w = d18[m]
        i_on = int(np.argmin(np.abs(ages[m] - on)))
        f = feats(w, i_on)
        lab = classify(f, th)
        events.append(dict(name=nm, onset=on, pre=float(pre), label=lab,
                           **{k: f[k] for k in ("rise", "S", "z")}))
        print(f"{nm} (онсет {on}): rise={f['rise']:.1f} S={f['S'] if f['S'] is None else round(f['S'],2)} "
              f"z={f['z']:.2f} -> {lab}", flush=True)
    for nm in CTRL_EVENTS:
        on = ONSETS[nm]
        m = (ages <= on + 2800) & (ages >= on + 800)
        w = d18[m]
        f = feats(w, len(w) - 20)
        lab = classify(f, th)
        ctrls.append(dict(name=f"стадиал-{nm}", label=lab, **{k: f[k] for k in ("rise", "S", "z")}))
        print(f"стадиал-{nm}: rise={f['rise']:.2f} z={f['z']:.2f} -> {lab}", flush=True)
    cls = [e for e in events if not e["label"].startswith("исключён")]
    lab_counts = {}
    for e in cls: lab_counts[e["label"]] = lab_counts.get(e["label"], 0) + 1
    n_fold = lab_counts.get("фолд", 0); n_osc = lab_counts.get("осциллятор", 0)
    n_none = lab_counts.get("нет рождения", 0)
    n = len(cls)
    pe2 = "a" if n_fold >= 11 else ("b" if n_osc >= 11 else "смешанный")
    transfer_dead = n_none >= 11
    ctl_none = sum(1 for c in ctrls if c["label"] == "нет рождения")
    pe3 = ctl_none >= 4; pe3_kill = ctl_none <= 2
    full = [e for e in cls if e["pre"] >= 1599]
    trunc = [e for e in cls if e["pre"] < 1599]
    fr_full = sum(1 for e in full if e["label"] == "фолд") / max(len(full), 1)
    fr_trunc = sum(1 for e in trunc if e["label"] == "фолд") / max(len(trunc), 1)
    ck["ngrip"] = dict(events=events, ctrls=ctrls, lab_counts=lab_counts, n=n,
                       verdicts=dict(PE2=pe2, transfer_dead=bool(transfer_dead),
                                     ctl_none=ctl_none, PE3=bool(pe3), PE3_killed=bool(pe3_kill),
                                     PE4=dict(full=fr_full, trunc=fr_trunc, n_full=len(full), n_trunc=len(trunc))))
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"\nМетки по {n} событиям: {lab_counts}")
    print(f"P-E2: ветвь ({pe2}) — фолд {n_fold}/{n}, осциллятор {n_osc}/{n}, нет рождения {n_none}/{n}"
          f"{' | ПЕРЕНОС МЁРТВ (>=11 нет рождения)' if transfer_dead else ''}")
    print(f"P-E3 (стадиальные контроли): {ctl_none}/5 -> {'ПОДТВЕРЖДЁН' if pe3 else ('УБИТ' if pe3_kill else 'не установлен')}")
    print(f"P-E4: доля фолда полные/трункированные = {fr_full:.2f} ({len(full)}) / {fr_trunc:.2f} ({len(trunc)})")
print(f"[{time.time()-t0:.0f}s]")
