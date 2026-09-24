"""EXT-001b — uniform NGRIP windows 800x400. Per PREREG (frozen 2026-08-26).
Recalibrate at 40-pre geometry, then blind uniform pass."""
import json, os, sys, time
import numpy as np

exec(open("/home/claude/ext001_run.py").read().split("t0 = time.time()")[0])  # feats, classify, cme_window, coarse, ONSETS, CTRL_EVENTS, XLS

CKPT_B = "/home/claude/ext001b_ckpt.json"
t0 = time.time()
ck = json.load(open(CKPT_B)) if os.path.exists(CKPT_B) else {}

def cme_window40(name, drifting, seed):
    w, ion = cme_window(name, drifting, seed)
    if w is None: return None, None
    lo = max(ion - 40, 0)
    hi = min(ion + 20, len(w))
    return w[lo:hi], ion - lo

# ---------- Phase A at 40-pre ----------
if "th" not in ck:
    Sf, St, zs = [], [], []
    for name, bag in (("fold", Sf), ("trans", St)):
        for i in (1, 2, 3):
            w, ion = cme_window40(name, True, 992000 + i + (0 if name == "fold" else 100))
            if w is None: continue
            f = feats(w, ion)
            bag.append(f["S"] if f["S"] is not None else -1)
            zs.append(f["z"])
            print(f"калибр {name}#{i}: S={f['S'] if f['S'] is None else round(f['S'],2)} rise={f['rise']:.1f} z={f['z']:.2f}", flush=True)
    rises = []
    for name in ("fold", "trans"):
        for i in (1, 2, 3):
            w, ion = cme_window40(name, False, 992500 + i + (0 if name == "fold" else 100))
            f = feats(w, ion)
            rises.append(f["rise"]); zs.append(f["z"])
    ok = all(s > 0 for s in Sf + St)
    alive = ok and min(Sf) > max(St)
    thS = float(np.sqrt(min(Sf) * max(St))) if alive else None
    thRise = 2.5 * max(rises)
    thR2 = 2.5 * float(np.percentile(zs, 99))
    ck["th"] = dict(thS=thS, S_alive=bool(alive), minS_fold=(min(Sf) if Sf else None),
                    maxS_trans=(max(St) if St else None), thRise=float(thRise), thR2=float(thR2))
    json.dump(ck, open(CKPT_B, "w"), default=float)
    print(f"ЗАМОРОЖЕНО (40-пре): S_alive={alive} thS={thS} thRise={thRise:.2f} thR2={thR2:.2f}", flush=True)
th = ck["th"]
if not th["S_alive"]:
    print("S-ножка мертва на 40-пре — NGRIP не вскрывается (P-F1 убит постановкой)."); sys.exit(0)

if "valid" not in ck:
    correct, ctl_ok = 0, 0
    for name, want in (("fold", "фолд"), ("trans", "непрерывный")):
        for i in (1, 2, 3, 4, 5):
            w, ion = cme_window40(name, True, 993000 + i + (0 if name == "fold" else 100))
            if w is None: continue
            lab = classify(feats(w, ion), th)
            correct += (lab == want)
            print(f"валид {name}#{i}: -> {lab}", flush=True)
    for j, name in enumerate(("fold", "trans", "fold", "trans", "fold", "trans")):
        w, ion = cme_window40(name, False, 993500 + j)
        lab = classify(feats(w, ion), th)
        ctl_ok += (lab == "нет рождения")
    pf1 = correct >= 8 and ctl_ok >= 5
    ck["valid"] = dict(correct=correct, ctl_ok=ctl_ok, PF1=bool(pf1),
                       PF1_killed=bool(correct <= 6 or ctl_ok <= 3))
    json.dump(ck, open(CKPT_B, "w"), default=float)
    print(f"P-F1: {correct}/10, контроли {ctl_ok}/6 -> {'ПОДТВЕРЖДЁН' if pf1 else 'УБИТ/не установлен — стоп'}", flush=True)
if not ck["valid"]["PF1"]:
    sys.exit(0)

# ---------- Phase B: uniform NGRIP pass ----------
if "ngrip" not in ck:
    import xlrd
    wb = xlrd.open_workbook(XLS); sh = wb.sheet_by_index(0)
    ages, d18 = [], []
    for r in range(61, sh.nrows):
        a, d = sh.cell_value(r, 0), sh.cell_value(r, 2)
        if isinstance(a, float) and isinstance(d, float):
            ages.append(a); d18.append(d)
    ages = np.array(ages); d18 = np.array(d18)
    order = np.argsort(-ages); ages, d18 = ages[order], d18[order]
    prev_full_fold = {"YD/PB", "GI-1", "GI-4", "GI-7", "GI-8", "GI-11", "GI-12", "GI-15"}
    prev_full = {"YD/PB", "GI-1", "GI-2", "GI-4", "GI-7", "GI-8", "GI-11", "GI-12", "GI-13", "GI-15", "GI-16"}
    names = sorted(ONSETS, key=lambda k: -ONSETS[k])
    older = {}
    for i, nm in enumerate(names):
        older[nm] = 60000.0 if i == 0 else ONSETS[names[i - 1]]
    events, ctrls = [], []
    for nm in names:
        on = ONSETS[nm]
        if older[nm] - 200 - on < 800:
            events.append(dict(name=nm, label="исключён")); continue
        m = (ages <= on + 800) & (ages >= on - 400)
        w = d18[m]
        i_on = int(np.argmin(np.abs(ages[m] - on)))
        f = feats(w, i_on)
        lab = classify(f, th)
        events.append(dict(name=nm, onset=on, label=lab, **{k: f[k] for k in ("rise", "S", "z")}))
        print(f"{nm}: rise={f['rise']:.1f} S={f['S'] if f['S'] is None else round(f['S'],2)} z={f['z']:.2f} -> {lab}", flush=True)
    for nm in CTRL_EVENTS:
        on = ONSETS[nm]
        m = (ages <= on + 2000) & (ages >= on + 800)
        w = d18[m]
        f = feats(w, len(w) - 20)
        lab = classify(f, th)
        ctrls.append(dict(name=f"стадиал-{nm}", label=lab, rise=f["rise"], z=f["z"]))
        print(f"стадиал-{nm}: rise={f['rise']:.2f} -> {lab}", flush=True)
    cls = [e for e in events if e["label"] != "исключён"]
    lab_counts = {}
    for e in cls: lab_counts[e["label"]] = lab_counts.get(e["label"], 0) + 1
    keep = sum(1 for e in cls if e["name"] in prev_full_fold and e["label"] == "фолд")
    full_all = [e for e in cls if e["name"] in prev_full]
    keep_full = sum(1 for e in full_all if e["label"] == "фолд")
    trunc6 = [e for e in cls if e["name"] not in prev_full]
    new_fold = sum(1 for e in trunc6 if e["label"] == "фолд")
    pf2 = keep_full >= 6; pf2_kill = keep_full <= 4
    pf3 = "a" if new_fold >= 2 else "b"
    ctl_none = sum(1 for c in ctrls if c["label"] == "нет рождения")
    pf4 = ctl_none >= 4; pf4_kill = ctl_none <= 2
    loo = all(sum(1 for e in full_all if e is not x and e["label"] == "фолд") >= 5 for x in full_all)
    ck["ngrip"] = dict(events=events, ctrls=ctrls, lab_counts=lab_counts,
                       verdicts=dict(keep_full=keep_full, keep_of_prev_fold=keep, new_fold=new_fold,
                                     PF2=bool(pf2), PF2_killed=bool(pf2_kill), PF3=pf3,
                                     ctl_none=ctl_none, PF4=bool(pf4), PF4_killed=bool(pf4_kill),
                                     loo_ok=bool(loo)))
    json.dump(ck, open(CKPT_B, "w"), default=float)
    print(f"\nМетки: {lab_counts}")
    print(f"P-F2 (фолд среди 11 ранее-полных): {keep_full}/11 -> {'ПОДТВЕРЖДЁН' if pf2 else ('УБИТ' if pf2_kill else 'не установлен')} (LOO={loo}; из прежних 8 фолдов сохранили {keep})")
    print(f"P-F3 (6 ранее-трункированных): новых фолдов {new_fold}/6 -> ветвь ({pf3})")
    print(f"P-F4 (контроли): {ctl_none}/5 -> {'ПОДТВЕРЖДЁН' if pf4 else ('УБИТ' if pf4_kill else 'не установлен')}")
print(f"[{time.time()-t0:.0f}s]")
