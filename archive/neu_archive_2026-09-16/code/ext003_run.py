"""EXT-003 — curated paleo transitions; EXT-004 — sapropel anoxia. Per PREREG (frozen 2026-08-27).
Inherits frozen feats/classify and EXT-001 thresholds (theta_S=5.12, theta_rise=1.99, theta_R2=4.85)."""
import json, time
import numpy as np
import pandas as pd

exec(open("/home/claude/ext001_run.py").read().split("t0 = time.time()")[0])   # feats, classify

TH = json.load(open("/home/claude/ext001_ckpt.json"))["th"]                    # frozen EXT-001 thresholds
t0 = time.time()
out = {"th": TH}

def window_resample(age, val, t_hi, t_lo, n=100):
    """Ages decrease toward present inside [t_lo, t_hi] (t_hi older). Resample to n uniform, time forward."""
    m = (age <= t_hi) & (age >= t_lo)
    if m.sum() < 10: return None
    a, v = age[m], val[m]
    o = np.argsort(-a)                     # time forward = decreasing age
    a, v = a[o], v[o]
    tt = -a                                # monotone increasing
    grid = np.linspace(tt[0], tt[-1], n)
    return np.interp(grid, tt, v)

# ================= EXT-003 =================
dp = pd.read_csv("deep-early-warnings-pnas/test_empirical/paleoclimate/data/transition_data.csv")
ev3, ct3 = [], []
for tsid in sorted(dp.tsid.unique()):
    d = dp[dp.tsid == tsid]
    rec = d.Record.iloc[0]
    age = d.Age.to_numpy(float); val = d.Proxy.to_numpy(float)
    tr = float(d.Transition.iloc[0])
    n_pre = int((age > tr).sum())
    if n_pre < 40:
        ev3.append(dict(tsid=int(tsid), rec=rec, label="исключён (N_pre<40)")); continue
    span = age.max() - age.min()
    pre = 0.4 * span; post = 0.1 * span
    w = window_resample(age, val, tr + pre, max(tr - post, age.min()))
    if w is None:
        ev3.append(dict(tsid=int(tsid), rec=rec, label="окно-провал")); continue
    f = feats(w, 80)
    lab = classify(f, TH)
    ev3.append(dict(tsid=int(tsid), rec=rec, label=lab, **{k: f[k] for k in ("rise", "S", "z")}))
    print(f"палео tsid={tsid} {rec!r}: rise={f['rise']:.1f} S={f['S'] if f['S'] is None else round(f['S'],2)} "
          f"z={f['z']:.2f} -> {lab}", flush=True)
    # control window where available
    if age.max() - tr >= 0.8 * span:
        wc = window_resample(age, val, tr + 0.8 * span, tr + 0.4 * span)
        if wc is not None:
            fc = feats(wc, 80)
            lc = classify(fc, TH)
            ct3.append(dict(tsid=int(tsid), label=lc, rise=fc["rise"]))
            print(f"  контроль: rise={fc['rise']:.2f} -> {lc}", flush=True)
cls3 = [e for e in ev3 if "label" in e and not e["label"].startswith(("исключён", "окно"))]
lc3 = {}
for e in cls3: lc3[e["label"]] = lc3.get(e["label"], 0) + 1
n3 = len(cls3)
ph = "a" if lc3.get("фолд", 0) >= 4 else ("b" if lc3.get("непрерывный", 0) >= 4 else "смешанный")
dead3 = lc3.get("нет рождения", 0) >= 4
c3n = sum(1 for c in ct3 if c["label"] == "нет рождения")
ph2 = len(ct3) > 0 and c3n >= np.ceil(2 * len(ct3) / 3)
ph2_kill = len(ct3) > 0 and c3n <= len(ct3) / 3
yd = next((e for e in cls3 if e["tsid"] == 3), None)
ph3 = yd is not None and yd["label"] == "фолд"
loo3 = all(sum(1 for e in cls3 if e is not x and e["label"] == "фолд") >= 3 for x in cls3) if ph == "a" else None
out["ext003"] = dict(events=ev3, ctrls=ct3, lab_counts=lc3,
                     verdicts=dict(PH=ph, transfer_dead=bool(dead3), ctl_none=c3n, n_ctl=len(ct3),
                                   PH2=bool(ph2), PH2_killed=bool(ph2_kill), PH3=bool(ph3), loo=loo3))
print(f"\nПАЛЕО метки ({n3}): {lc3} | P-H ветвь ({ph}){' | ПЕРЕНОС МЁРТВ' if dead3 else ''}")
print(f"P-H2 контроли: {c3n}/{len(ct3)} -> {'ПОДТВЕРЖДЁН' if ph2 else ('УБИТ' if ph2_kill else 'не установлен')}")
print(f"P-H3 (Конец Younger Dryas = фолд): {ph3}")

# ================= EXT-004 =================
da = pd.read_csv("deep-early-warnings-pnas/test_empirical/anoxia/data/data_transitions.csv")
res4 = {}
for proxy in ("Mo [ppm]", "U [ppm]"):
    ev4, ct4 = [], []
    for tsid in sorted(da.tsid.unique()):
        d = da[da.tsid == tsid]
        age = d["Age [ka BP]"].to_numpy(float); val = d[proxy].to_numpy(float)
        ts_, te_ = float(d.t_transition_start.iloc[0]), float(d.t_transition_end.iloc[0])
        span = age.max() - age.min()
        w = window_resample(age, val, ts_ + 0.4 * span, max(te_ - 0.1 * span, age.min()))
        if w is None:
            ev4.append(dict(tsid=int(tsid), label="окно-провал")); continue
        # onset index = nearest resampled position of transition midpoint
        t_hi = ts_ + 0.4 * span; t_lo = max(te_ - 0.1 * span, age.min())
        mid = 0.5 * (ts_ + te_)
        i_on = int(round((t_hi - mid) / (t_hi - t_lo) * 99))
        i_on = min(max(i_on, 15), 92)
        f = feats(w, i_on)
        lab = classify(f, TH)
        ev4.append(dict(tsid=int(tsid), ID=d.ID.iloc[0], core=d.Core.iloc[0], label=lab, i_on=i_on,
                        **{k: f[k] for k in ("rise", "S", "z")}))
        if proxy.startswith("Mo"):
            print(f"аноксия tsid={tsid} {d.ID.iloc[0]}/{d.Core.iloc[0]}: rise={f['rise']:.1f} "
                  f"S={f['S'] if f['S'] is None else round(f['S'],2)} z={f['z']:.2f} -> {lab}", flush=True)
        if age.max() - ts_ >= 0.8 * span:
            wc = window_resample(age, val, ts_ + 0.8 * span, ts_ + 0.4 * span)
            if wc is not None:
                fc = feats(wc, 80)
                ct4.append(dict(tsid=int(tsid), label=classify(fc, TH)))
    res4[proxy] = dict(events=ev4, ctrls=ct4)
evM = [e for e in res4["Mo [ppm]"]["events"] if e["label"] != "окно-провал"]
lcM = {}
for e in evM: lcM[e["label"]] = lcM.get(e["label"], 0) + 1
pj = "a" if lcM.get("фолд", 0) >= 7 else ("b" if lcM.get("непрерывный", 0) >= 7 else "смешанный")
dead4 = lcM.get("нет рождения", 0) >= 7
ctM = res4["Mo [ppm]"]["ctrls"]
c4n = sum(1 for c in ctM if c["label"] == "нет рождения")
pj2 = len(ctM) > 0 and c4n >= np.ceil(2 * len(ctM) / 3)
pj2_kill = len(ctM) > 0 and c4n <= len(ctM) / 3
labU = {e["tsid"]: e["label"] for e in res4["U [ppm]"]["events"]}
agree = sum(1 for e in evM if labU.get(e["tsid"]) == e["label"])
pj3 = agree >= 8
out["ext004"] = dict(res={k: v for k, v in res4.items()}, lab_counts_Mo=lcM,
                     verdicts=dict(PJ=pj, transfer_dead=bool(dead4), ctl_none=c4n, n_ctl=len(ctM),
                                   PJ2=bool(pj2), PJ2_killed=bool(pj2_kill), agree_MoU=agree, PJ3=bool(pj3)))
json.dump(out, open("/home/claude/ext003_004_results.json", "w"), default=float)
print(f"\nАНОКСИЯ метки Mo ({len(evM)}): {lcM} | P-J ветвь ({pj}){' | ПЕРЕНОС МЁРТВ' if dead4 else ''}")
print(f"P-J2 контроли: {c4n}/{len(ctM)} -> {'ПОДТВЕРЖДЁН' if pj2 else ('УБИТ' if pj2_kill else 'не установлен')}")
print(f"P-J3 (согласие Mo/U): {agree}/13 -> {pj3}")
print(f"[{time.time()-t0:.0f}s]")
