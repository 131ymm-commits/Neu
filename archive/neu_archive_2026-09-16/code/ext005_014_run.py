"""EXT-005..014 batch on real GitHub data. Per PREREG (frozen 2026-08-27)."""
import json, os, time, glob
import numpy as np
import pandas as pd
from scipy.signal import welch
from scipy.optimize import curve_fit

exec(open("/home/claude/ext001_run.py").read().split("t0 = time.time()")[0])   # feats, classify
TH = json.load(open("/home/claude/ext001_ckpt.json"))["th"]
RNG = np.random.default_rng(424244)
CK = "/home/claude/ext005_014_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()
B = "/home/claude"

def dphi_of(seg, lag):
    seg = np.asarray(seg, float)
    t = np.arange(len(seg))
    res = seg - np.polyval(np.polyfit(t, seg, 1), t)
    if res.std() == 0: return None
    u = res[lag:]; v = res[:-lag]
    phi = np.arctan2(v, u)
    return np.angle(np.exp(1j * np.diff(phi)))

def wind_fire(seg, lag, nsur=200):
    d = dphi_of(seg, lag)
    if d is None: return None, None, None
    sd = d.std() + 1e-12
    z = float(abs(d.sum()) / (sd * np.sqrt(d.size)))
    eps = RNG.choice([-1.0, 1.0], size=(nsur, d.size))
    zs = np.abs(eps @ d) / (sd * np.sqrt(d.size))
    th = 2.5 * float(np.percentile(zs, 99))
    return z, th, bool(z >= th)

def resample_series(t_, v_, n=100):
    grid = np.linspace(t_[0], t_[-1], n)
    return np.interp(grid, t_, v_)

# ---------------- EXT-005 Bonn EEG ----------------
if "e005" not in ck:
    res = {}
    for grp in ("A_Z", "B_O", "C_N", "D_F", "E_S"):
        fires = 0; files = sorted(glob.glob(f"{B}/EEG-Epilepsy-Datasets/bonn/{grp}/*.txt")) + \
                          sorted(glob.glob(f"{B}/EEG-Epilepsy-Datasets/bonn/{grp}/*.TXT"))
        for fp in files:
            x = np.loadtxt(fp)
            nf = 0
            for s0 in (0, 1024, 2048, 3072):
                _, _, f = wind_fire(x[s0:s0 + 1024], 6)
                nf += bool(f)
            fires += (nf >= 2)
        res[grp] = dict(n=len(files), fires=fires, rate=fires / max(len(files), 1))
        print(f"E005 {grp}: {fires}/{len(files)}", flush=True)
    fE = res["E_S"]["rate"]; fH = (res["A_Z"]["fires"] + res["B_O"]["fires"]) / (res["A_Z"]["n"] + res["B_O"]["n"])
    pk1 = (fE - fH) >= 0.4; pk1_kill = (fE - fH) <= 0.1
    pk2 = fH <= 0.25; pk2_kill = fH >= 0.5
    ck["e005"] = dict(res=res, fE=fE, fH=fH, PK1=bool(pk1), PK1_killed=bool(pk1_kill),
                      PK2=bool(pk2), PK2_killed=bool(pk2_kill))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"E005: fire(судороги)={fE:.2f} fire(здоровые)={fH:.2f} | P-K1 {'✓' if pk1 else ('УБИТ' if pk1_kill else '?')} "
          f"P-K2 {'✓' if pk2 else ('УБИТ' if pk2_kill else '?')} [{time.time()-t0:.0f}s]", flush=True)

# ---------------- EXT-006 COVID ----------------
if "e006" not in ck:
    c = pd.read_csv(f"{B}/COVID-19/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv")
    g = c.groupby("Country/Region").sum(numeric_only=True)
    g = g[[col for col in g.columns if "/" in col]]
    top = g.iloc[:, -1].sort_values(ascending=False).head(20).index.tolist()
    labs, rows, ctls = {}, [], []
    for cn in top:
        cum = g.loc[cn].to_numpy(float)
        new = np.clip(np.diff(cum, prepend=0), 0, None)
        sm = pd.Series(new).rolling(7, min_periods=1).mean().to_numpy()
        on = np.flatnonzero(sm >= 50)
        if on.size == 0:
            rows.append(dict(country=cn, label="нет онсета")); continue
        i0 = int(on[0])
        lo = i0 - 40
        w = sm[max(lo, 0): i0 + 60]
        if lo < 0: w = np.concatenate([np.zeros(-lo), w])
        w = w[:100]
        if len(w) < 100: w = np.concatenate([w, np.full(100 - len(w), w[-1])])
        f = feats(w, 40)
        lab = classify(f, TH)
        labs[lab] = labs.get(lab, 0) + 1
        rows.append(dict(country=cn, onset_day=i0, label=lab, **{k: f[k] for k in ("rise", "S", "z")}))
        if i0 >= 60:
            q = resample_series(np.arange(i0 - 10), sm[:i0 - 10], 100)
            lc = classify(feats(q, 80), TH)
            ctls.append(dict(country=cn, label=lc))
    ncont = labs.get("непрерывный", 0)
    pl1 = ncont >= 12
    pl1_kill = labs.get("фолд", 0) >= 10 or labs.get("нет рождения", 0) >= 10
    cn_ = sum(1 for x in ctls if x["label"] == "нет рождения")
    pl2 = len(ctls) > 0 and cn_ >= np.ceil(2 * len(ctls) / 3)
    pl2_kill = len(ctls) > 0 and cn_ <= len(ctls) / 3
    ck["e006"] = dict(rows=rows, ctls=ctls, labs=labs, PL1=bool(pl1), PL1_killed=bool(pl1_kill),
                      ctl_none=cn_, n_ctl=len(ctls), PL2=bool(pl2), PL2_killed=bool(pl2_kill))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"E006: метки={labs} контроли {cn_}/{len(ctls)} | P-L1 {'✓' if pl1 else ('УБИТ' if pl1_kill else '?')} "
          f"P-L2 {'✓' if pl2 else ('УБИТ' if pl2_kill else '?')} [{time.time()-t0:.0f}s]", flush=True)

# ---------------- EXT-007 sunspots ----------------
def lorentz(w, A_, G, w0, C):
    return A_ * G * G / (G * G + (w - w0) ** 2) + C

def tau_sp(x, per, fs, nper):
    res = np.asarray(x, float); res = res - res.mean()
    f, P = welch(res, fs=fs, nperseg=min(nper, len(res)))
    w = 2 * np.pi * f
    w0 = 2 * np.pi / per
    m = (w >= 0.5 * w0) & (w <= 1.5 * w0)
    if m.sum() < 6: return None
    try:
        popt, _ = curve_fit(lorentz, w[m], P[m], p0=[P[m].max(), w0 / 6, w0, P[m].min()],
                            bounds=([0, (w[1]-w[0]) / 2, 0.5 * w0, 0], [np.inf, w0, 1.5 * w0, np.inf]), maxfev=20000)
        return float(1.0 / popt[1])
    except Exception:
        return None

if "e007" not in ck:
    s = pd.read_csv(f"{B}/Rdatasets/csv/datasets/sunspot.month.csv")["value"].to_numpy(float)
    wins = [s[i:i + 786] for i in range(0, len(s) - 786 + 1, 262)]
    fr = [wind_fire(w, 21)[2] for w in wins]
    rate = np.mean([bool(x) for x in fr])
    pm1 = rate >= 0.9; pm1_kill = rate <= 0.5
    tau = tau_sp(s, 131.0, 1.0, 2048)
    ratio = tau / 131.0 if tau else None
    pm2 = ratio is not None and 1 <= ratio <= 8
    pm2_kill = ratio is not None and not (0.5 <= ratio <= 20)
    ck["e007"] = dict(n_win=len(wins), rate=float(rate), tau=tau, ratio=ratio,
                      PM1=bool(pm1), PM1_killed=bool(pm1_kill), PM2=bool(pm2), PM2_killed=bool(pm2_kill))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"E007: намотка {rate:.2f} окон | τ/период={ratio} | P-M1 {'✓' if pm1 else ('УБИТ' if pm1_kill else '?')} "
          f"P-M2 {'✓' if pm2 else ('УБИТ' if pm2_kill else '?')} [{time.time()-t0:.0f}s]", flush=True)

# ---------------- EXT-008 LR04 MPT ----------------
if "e008" not in ck:
    lr = np.loadtxt(f"{B}/pleistocene/orig/LR04/LR04/total.tab", skiprows=59, usecols=(0, 1), encoding="latin-1")
    age, d18 = lr[:, 0], lr[:, 1]
    def dom_period(a_lo, a_hi):
        m = (age >= a_lo) & (age <= a_hi)
        g = np.arange(a_lo, a_hi, 2.0)
        x = np.interp(g, age[m], d18[m])
        x = x - x.mean()
        f, P = welch(x, fs=0.5, nperseg=min(256, len(x)))
        per = 1 / np.maximum(f, 1e-9)
        band = (per >= 20) & (per <= 200)
        ip = int(np.argmax(P[band]))
        return float(per[band][ip]), x
    pP, xpre = dom_period(1500, 2500)
    pQ, xpost = dom_period(0, 1000)
    pn1 = (35 <= pP <= 50) and (80 <= pQ <= 130)
    pn1_kill = not pn1 and (pP >= 80 or pQ <= 50)
    zpre = wind_fire(xpre, max(2, int(round(pP / 2 / 6.28 / 1))), )[0] if False else None
    z1, _, _ = wind_fire(xpre, max(2, int(round(pP / 2 / 6.283))))
    z2, _, _ = wind_fire(xpost, max(2, int(round(pQ / 2 / 6.283))))
    ck["e008"] = dict(per_pre=pP, per_post=pQ, z_pre=z1, z_post=z2,
                      PN1=bool(pn1), PN1_killed=bool(pn1_kill), PN2=bool(z2 is not None and z1 is not None and z2 >= z1))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"E008: период PRE={pP:.0f} kyr POST={pQ:.0f} kyr | z {z1:.1f}->{z2:.1f} | "
          f"P-N1 {'✓' if pn1 else ('УБИТ' if pn1_kill else '?')} [{time.time()-t0:.0f}s]", flush=True)

# ---------------- EXT-009 EPICA replication ----------------
def read_wdc(path, cols):
    rows = []
    for ln in open(path, encoding="latin-1"):
        p = ln.split()
        if len(p) >= cols:
            try:
                rows.append([float(x) for x in p[:cols]])
            except ValueError:
                pass
    return np.array(rows)

if "e009" not in ck:
    co2 = read_wdc(f"{B}/pleistocene/orig/EPICA/edc-co2-2008.txt", 2)
    co2 = co2[(co2[:, 0] > 0) & (co2[:, 0] < 810000)]
    deu_raw = read_wdc(f"{B}/pleistocene/orig/EPICA/edc3deuttemp2007.txt", 4)
    deu = deu_raw[(deu_raw[:, 2] > 0) & (deu_raw[:, 2] < 810000)][:, [2, 3]]
    ext3 = {17.0: "фолд", 135.0: "непрерывный", 242.0: "фолд", 334.1: "осциллятор"}
    agree, rows = 0, []
    for pname, arr, vcol in (("CO2", co2, 1), ("dD", deu, 1)):
        a_ka = arr[:, 0] / 1000.0 if arr[:, 0].max() > 5000 else arr[:, 0]
        v = arr[:, vcol]
        for on, want in ext3.items():
            m = (a_ka <= on + 40) & (a_ka >= on - 10)
            if m.sum() < 25:
                rows.append(dict(proxy=pname, onset=on, label="исключён(<25)")); continue
            aa, vv = a_ka[m], v[m]
            o = np.argsort(-aa)
            w = resample_series(-aa[o], vv[o], 100)
            f = feats(w, 80)
            lab = classify(f, TH)
            rows.append(dict(proxy=pname, onset=on, label=lab, want=want,
                             **{k: f[k] for k in ("rise", "S", "z")}))
            agree += (lab == want)
            print(f"E009 {pname} T@{on}ka: rise={f['rise']:.1f} S={f['S'] if f['S'] is None else round(f['S'],2)} "
                  f"z={f['z']:.2f} -> {lab} (EXT-003: {want})", flush=True)
    t4 = [r for r in rows if r.get("onset") == 334.1 and r.get("label") == "осциллятор"]
    po1 = agree >= 4; po1_kill = agree <= 1
    ck["e009"] = dict(rows=rows, agree=agree, PO1=bool(po1), PO1_killed=bool(po1_kill), PO2=bool(len(t4) >= 1))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"E009: совпадений {agree}/8 | P-O1 {'✓' if po1 else ('УБИТ' if po1_kill else '?')} P-O2 {len(t4)>=1} [{time.time()-t0:.0f}s]", flush=True)

# ---------------- EXT-010/011 measles ----------------
STATES = ["NEW YORK", "CALIFORNIA", "PENNSYLVANIA", "ILLINOIS", "OHIO", "TEXAS",
          "MICHIGAN", "NEW JERSEY", "MASSACHUSETTS", "NORTH CAROLINA", "INDIANA", "MISSOURI"]
if "e010" not in ck or "e011" not in ck:
    m = pd.read_csv(f"{B}/blogR/data/measles_incidence.csv", skiprows=2, na_values="-")
    per_state = {}
    for st in STATES:
        d = m[["YEAR", "WEEK", st]].copy()
        d[st] = d[st].interpolate(limit_direction="both")
        per_state[st] = d
    # E010: rotation death
    r10 = {}
    for st in STATES:
        d = per_state[st]
        def zmed(y0, y1):
            x = d[(d.YEAR >= y0) & (d.YEAR <= y1)][st].to_numpy(float)
            zs = []
            for i in range(0, len(x) - 260 + 1, 130):
                z, _, _ = wind_fire(x[i:i + 260], 8)
                if z is not None: zs.append(z)
            return float(np.median(zs)) if zs else None
        zp, zq = zmed(1948, 1963), zmed(1968, 1983)
        r10[st] = (zp, zq)
        print(f"E010 {st}: z_pre={zp:.1f} z_post={zq:.1f}", flush=True)
    nwin = sum(1 for st in STATES if r10[st][0] is not None and r10[st][1] is not None and r10[st][0] > r10[st][1])
    pp1 = nwin >= 10; pp1_kill = nwin <= 6
    medp = np.median([r10[st][0] for st in STATES]); medq = np.median([r10[st][1] for st in STATES])
    ck["e010"] = dict(r10={k: v for k, v in r10.items()}, nwin=nwin, med_pre=float(medp), med_post=float(medq),
                      PP1=bool(pp1), PP1_killed=bool(pp1_kill), PP2=bool(medp >= 2 * medq))
    # E011: flip via alternation of yearly totals
    def altfrac(st, y0, y1):
        d = per_state[st]
        yr = d[(d.YEAR >= y0) & (d.YEAR <= y1)].groupby("YEAR")[st].sum()
        s = np.sign(np.diff(yr.to_numpy(float)))
        s = s[s != 0]
        if len(s) < 8: return None
        return float(np.mean(s[1:] != s[:-1]))
    npre = sum(1 for st in STATES if (a := altfrac(st, 1948, 1963)) is not None and a >= 0.75)
    npost = sum(1 for st in STATES if (a := altfrac(st, 1968, 1983)) is not None and a >= 0.75)
    pq1 = npre >= 8 and npost <= 3
    pq1_kill = npre <= 4 or npost >= 8
    ck["e011"] = dict(npre=npre, npost=npost, PQ1=bool(pq1), PQ1_killed=bool(pq1_kill),
                      alts_pre={st: altfrac(st, 1948, 1963) for st in STATES},
                      alts_post={st: altfrac(st, 1968, 1983) for st in STATES})
    json.dump(ck, open(CK, "w"), default=float)
    print(f"E010: z_pre>z_post в {nwin}/12 (медианы {medp:.1f}/{medq:.1f}) | P-P1 {'✓' if pp1 else ('УБИТ' if pp1_kill else '?')}", flush=True)
    print(f"E011: A>=0.75 до {npre}/12, после {npost}/12 | P-Q1 {'✓' if pq1 else ('УБИТ' if pq1_kill else '?')} [{time.time()-t0:.0f}s]", flush=True)

# ---------------- EXT-012 faithful ----------------
if "e012" not in ck:
    fa = pd.read_csv(f"{B}/Rdatasets/csv/datasets/faithful.csv")["eruptions"].to_numpy(float)
    s = np.sign(fa - np.median(fa)); s = s[s != 0]
    A = float(np.mean(s[1:] != s[:-1]))
    pr1 = A >= 0.60; pr1_kill = A <= 0.52
    after_short = float(np.mean(s[1:][s[:-1] < 0] > 0)) if (s[:-1] < 0).any() else None
    after_long = float(np.mean(s[1:][s[:-1] > 0] < 0)) if (s[:-1] > 0).any() else None
    ck["e012"] = dict(A=A, n=len(s) - 1, PR1=bool(pr1), PR1_killed=bool(pr1_kill),
                      after_short=after_short, after_long=after_long, PR2=bool(after_short and after_long and after_short > after_long))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"E012: A={A:.3f} (n={len(s)-1}) | после-короткого {after_short:.2f} vs после-длинного {after_long:.2f} | "
          f"P-R1 {'✓' if pr1 else ('УБИТ' if pr1_kill else '?')} [{time.time()-t0:.0f}s]", flush=True)

# ---------------- EXT-013 lynx ----------------
if "e013" not in ck:
    lx = pd.read_csv(f"{B}/Rdatasets/csv/datasets/lynx.csv")["value"].to_numpy(float)
    wins = [lx, lx[:57], lx[57:]]
    fires = [wind_fire(w, 2)[2] for w in wins]
    n_f = sum(bool(x) for x in fires)
    ps1 = n_f >= 2; ps1_kill = n_f == 0
    tau = tau_sp(lx, 9.6, 1.0, 64)
    ratio = tau / 9.6 if tau else None
    ck["e013"] = dict(fires=[bool(x) for x in fires], n=n_f, tau=tau, ratio=ratio,
                      PS1=bool(ps1), PS1_killed=bool(ps1_kill), PS2=bool(ratio is not None and 1 <= ratio <= 10))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"E013: намотка {n_f}/3 окон | τ/период={ratio} | P-S1 {'✓' if ps1 else ('УБИТ' if ps1_kill else '?')} [{time.time()-t0:.0f}s]", flush=True)

# ---------------- EXT-014 Nile kink v5 ----------------
def kink(ks, Ms):
    best = None
    for bi in range(3, len(ks) - 3):
        s1 = np.polyfit(ks[:bi + 1], Ms[:bi + 1], 1)[0]
        s2 = np.polyfit(ks[bi:], Ms[bi:], 1)[0]
        r = (np.sum((Ms[:bi + 1] - np.polyval(np.polyfit(ks[:bi + 1], Ms[:bi + 1], 1), ks[:bi + 1])) ** 2)
             + np.sum((Ms[bi:] - np.polyval(np.polyfit(ks[bi:], Ms[bi:], 1), ks[bi:])) ** 2))
        if best is None or r < best[0]:
            best = (r, abs(s2 - s1), float(ks[bi]))
    return best[1], best[2]

if "e014" not in ck:
    ni = pd.read_csv(f"{B}/Rdatasets/csv/datasets/Nile.csv")
    yr = ni["time"].to_numpy(float); x = ni["value"].to_numpy(float)
    kd, bp = kink(yr, x)
    xm = x - x.mean()
    phi = float(np.corrcoef(xm[:-1], xm[1:])[0, 1])
    sig = float(np.std(xm[1:] - phi * xm[:-1]))
    flag_phi = phi >= 0.99
    ksur = []
    for _ in range(200):
        e = RNG.normal(0, sig, len(x))
        y = np.empty(len(x)); y[0] = e[0]
        for i in range(1, len(x)): y[i] = phi * y[i - 1] + e[i]
        ksur.append(kink(yr, y + x.mean())[0])
    Kadd = kd - float(np.median(ksur))
    thr = 2.5 * float(np.percentile(ksur, 99))
    fire = Kadd >= thr
    pos_ok = 1893 <= bp <= 1903
    pt1 = fire and pos_ok
    pt1_kill = (not pos_ok) or (not fire)
    ck["e014"] = dict(k_data=kd, bp=bp, phi=phi, Kadd=Kadd, thr=thr, fire=bool(fire), flag_phi=bool(flag_phi),
                      PT1=bool(pt1), PT1_killed=bool(pt1_kill))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"E014: излом при {bp:.0f} (нужно 1893–1903), K_add={Kadd:.2f} против порога {thr:.2f}, φ̂={phi:.2f} | "
          f"P-T1 {'✓' if pt1 else 'УБИТ'} [{time.time()-t0:.0f}s]", flush=True)

print(f"\n[{time.time()-t0:.0f}s] батч готов -> {CK}")
