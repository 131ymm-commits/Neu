"""PRE-010b — v2-ext transfer: COVID 20 rows + paleo tsid8 + atlas v2. Per PREREG (frozen 2026-08-31)."""
import json, os, time
import numpy as np
import pandas as pd

exec(open("/home/claude/ext001_run.py").read().split("t0 = time.time()")[0])   # feats, classify, LAG_R2
TH = json.load(open("/home/claude/ext001_ckpt.json"))["th"]
TH_T, TH_AEXT = 2.0, 3.0
CK = "/home/claude/pre010b_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()

def ext_stats(win, i_on):
    """T (full turns) and A_ext (RMS/sigma_E) on the same whole-window residual as feats' z."""
    N = len(win)
    E = win[:max(i_on - 5, 10)]
    t = np.arange(len(E))
    res_e = E - np.polyval(np.polyfit(t, E, 1), t)
    sE = 1.4826 * np.median(np.abs(res_e - np.median(res_e))) + 1e-12
    t2 = np.arange(N)
    r2res = win - np.polyval(np.polyfit(t2, win, 1), t2)
    u = r2res[LAG_R2:]; v = r2res[:-LAG_R2]
    phi = np.arctan2(v, u)
    dphi = np.angle(np.exp(1j * np.diff(phi)))
    T = float(abs(dphi.sum()) / (2 * np.pi))
    A = float(np.sqrt(np.mean(r2res ** 2)) / sE)
    return T, A

def label_v2(f, T, A):
    if f["z"] >= TH["thR2"] and T >= TH_T and A >= TH_AEXT: return "осциллятор"
    if f["rise"] < TH["thRise"]: return "нет рождения"
    if f["S"] is not None and f["S"] >= TH["thS"]: return "фолд"
    return "непрерывный"

# ---------- COVID windows exactly as e006 ----------
if "covid" not in ck:
    stored = {r["country"]: r for r in json.load(open("/home/claude/ext005_014_ckpt.json"))["e006"]["rows"]}
    c = pd.read_csv("/home/claude/COVID-19/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv")
    g = c.groupby("Country/Region").sum(numeric_only=True)
    g = g[[col for col in g.columns if "/" in col]]
    top = g.iloc[:, -1].sort_values(ascending=False).head(20).index.tolist()
    rows, mism = [], []
    for cn in top:
        cum = g.loc[cn].to_numpy(float)
        new = np.clip(np.diff(cum, prepend=0), 0, None)
        sm = pd.Series(new).rolling(7, min_periods=1).mean().to_numpy()
        on = np.flatnonzero(sm >= 50)
        if on.size == 0: continue
        i0 = int(on[0]); lo = i0 - 40
        w = sm[max(lo, 0): i0 + 60]
        if lo < 0: w = np.concatenate([np.zeros(-lo), w])
        w = w[:100]
        if len(w) < 100: w = np.concatenate([w, np.full(100 - len(w), w[-1])])
        f = feats(w, 40)
        lab1 = classify(f, TH)
        if cn in stored and lab1 != stored[cn]["label"]: mism.append(cn)
        T, A = ext_stats(w, 40)
        lab2 = label_v2(f, T, A)
        rows.append(dict(country=cn, v1=lab1, v2=lab2, T=T, A=A, z=f["z"], rise=f["rise"], S=f["S"]))
        print(f"{cn}: v1={lab1} | T={T:.2f} A={A:.1f} -> v2={lab2}", flush=True)
    ck["covid"] = dict(rows=rows, sanity_mismatch=mism)
    json.dump(ck, open(CK, "w"), default=float)
    print(f"санити против e006: {20 - len(mism)}/20 (расхождения: {mism}) [{time.time()-t0:.0f}s]", flush=True)

# ---------- paleo tsid8 ----------
if "paleo8" not in ck:
    dp = pd.read_csv("/home/claude/deep-early-warnings-pnas/test_empirical/paleoclimate/data/transition_data.csv")
    d = dp[dp.tsid == 8]
    age = d.Age.to_numpy(float); val = d.Proxy.to_numpy(float)
    tr = float(d.Transition.iloc[0])
    span = age.max() - age.min()
    m = (age <= tr + 0.4 * span) & (age >= max(tr - 0.1 * span, age.min()))
    a, v = age[m], val[m]
    o = np.argsort(-a); a, v = a[o], v[o]
    tt = -a
    w = np.interp(np.linspace(tt[0], tt[-1], 100), tt, v)
    f = feats(w, 80)
    T, A = ext_stats(w, 80)
    lab2 = label_v2(f, T, A)
    ck["paleo8"] = dict(v1="осциллятор", z=f["z"], T=T, A=A, v2=lab2)
    json.dump(ck, open(CK, "w"), default=float)
    print(f"палео tsid8: z={f['z']:.2f} T={T:.2f} A={A:.1f} -> v2={lab2} [{time.time()-t0:.0f}s]", flush=True)

# ---------- verdicts b1/b2 ----------
rows = ck["covid"]["rows"]
osc1 = [r for r in rows if r["v1"] == "осциллятор"]
lost = [r["country"] for r in osc1 if r["v2"] != "осциллятор"]
gain = [r["country"] for r in rows if r["v1"] != "осциллятор" and r["v2"] == "осциллятор"]
nl = len(lost)
b1 = nl >= 3
b2 = nl == 0
ck["verdicts_b12"] = dict(n_osc_v1=len(osc1), lost=lost, gained=gain, PP10b1=bool(b1), PP10b2=bool(b2))
json.dump(ck, open(CK, "w"), default=float)
print(f"\nP-P10b1/b2: из {len(osc1)} осцилляторов v1 потеряли метку {nl} ({lost}); приобрели (обязано быть 0): {gain}")
print("вердикт: " + ("P-P10b1 ПОДТВЕРЖДЁН (дуги кривизны существуют)" if b1 else
      ("P-P10b2 ПОДТВЕРЖДЁН (диагноз кривизны пересматривается)" if b2 else "не установлено (1–2 потери)")))
print(f"[{time.time()-t0:.0f}s] -> {CK}")
