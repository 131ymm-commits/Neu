"""EXT-016 (v2 true positives on 19 rate ramps) + EXT-018 (quasi-static staircase). Per PREREG (frozen 2026-09-01)."""
import json, os, glob, re, time
import numpy as np

RNG = np.random.default_rng(20260904)
CK = "/home/claude/ext016_018_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()
TB = "/home/claude/deep-early-warnings-pnas/test_empirical/thermoacoustic/data/thermo_experiments"

def wind_T(seg, lag, nsur=200):
    seg = np.asarray(seg, float)
    t = np.arange(len(seg))
    res = seg - np.polyval(np.polyfit(t, seg, 1), t)
    if res.std() == 0: return None
    u = res[lag:]; v = res[:-lag]
    phi = np.arctan2(v, u)
    d = np.angle(np.exp(1j * np.diff(phi)))
    sd = d.std() + 1e-12
    z = float(abs(d.sum()) / (sd * np.sqrt(d.size)))
    eps = RNG.choice([-1.0, 1.0], size=(nsur, d.size))
    zs = np.abs(eps @ d) / (sd * np.sqrt(d.size))
    th = 2.5 * float(np.percentile(zs, 99))
    T = float(abs(d.sum()) / (2 * np.pi))
    rms = float(np.sqrt(np.mean(res ** 2)))
    return dict(z=z, th=th, T=T, rms=rms)

def sE_of(seg):
    seg = np.asarray(seg, float)
    t = np.arange(len(seg))
    res = seg - np.polyval(np.polyfit(t, seg, 1), t)
    return 1.4826 * float(np.median(np.abs(res - np.median(res)))) + 1e-12

def v2label(seg, sE, lag=10):
    w = wind_T(seg, lag)
    if w is None: return None, None
    A = w["rms"] / sE
    fire = (w["z"] >= w["th"]) and (w["T"] >= 2.0) and (A >= 3.0)
    return bool(fire), dict(z=w["z"], th=w["th"], T=w["T"], A=A)

# ---------------- EXT-016 ----------------
if "e016" not in ck:
    onsets = {r["idx"]: r for r in json.load(open("/home/claude/ver008_results.json"))["rows"] if r.get("t_rel") is not None}
    log = open(f"{TB}/Rate dependent transitions/pressure data/log.txt", encoding="latin-1").read()
    rows = []
    for fp in sorted(glob.glob(f"{TB}/Rate dependent transitions/pressure data/[0-9]*.txt"),
                     key=lambda s: int(re.findall(r"(\d+)\.txt", s)[0])):
        idx = int(re.findall(r"(\d+)\.txt", fp)[0])
        if idx not in onsets: continue
        d = np.loadtxt(fp, encoding="latin-1")
        if d.ndim != 2: continue
        t, p = d[:, 0] - d[0, 0], d[:, 1]
        dt = np.median(np.diff(t[:1000])); fs = 1.0 / dt
        ton = onsets[idx]["t_rel"]
        early_flag = ton < 6.0
        i_post = slice(int((ton + 1.0) * fs), int((ton + 3.0) * fs))
        i_pre = slice(int(2.0 * fs), int(4.0 * fs))
        if len(p[i_post]) < 1000:
            rows.append(dict(idx=idx, skip="post-окно вне записи")); continue
        sE = sE_of(p[i_pre]) if not early_flag else None
        if sE is None:
            rows.append(dict(idx=idx, skip="онсет слишком ранний — нет тихой зоны")); continue
        post_fire, post_d = v2label(p[i_post], sE)
        pre_fire, pre_d = v2label(p[i_pre], sE)
        rows.append(dict(idx=idx, rate=onsets[idx]["rate"], post=post_fire, pre=pre_fire,
                         post_T=post_d["T"], post_A=post_d["A"], post_z=post_d["z"], pre_z=pre_d["z"], pre_T=pre_d["T"]))
        print(f"рампа #{idx}: пост z={post_d['z']:.1f} T={post_d['T']:.0f} A={post_d['A']:.0f} -> "
              f"{'ОСЦ' if post_fire else 'нет'} | пре -> {'огонь' if pre_fire else 'тихо'} [{time.time()-t0:.0f}s]", flush=True)
    ok = [r for r in rows if "skip" not in r]
    n_post = sum(1 for r in ok if r["post"]); n_pre = sum(1 for r in ok if r["pre"])
    pb1a = len(ok) > 0 and n_post / len(ok) >= 0.8
    pb1a_kill = len(ok) > 0 and n_post / len(ok) <= 0.5
    pb1b = len(ok) > 0 and n_pre / len(ok) <= 0.3
    pb1b_kill = len(ok) > 0 and n_pre / len(ok) >= 0.6
    ck["e016"] = dict(rows=rows, n_ok=len(ok), n_post=n_post, n_pre=n_pre,
                      PB1a=bool(pb1a), PB1a_killed=bool(pb1a_kill), PB1b=bool(pb1b), PB1b_killed=bool(pb1b_kill))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"E016: пост-осц {n_post}/{len(ok)}, пре-огней {n_pre}/{len(ok)} | "
          f"P-B1a {'✓' if pb1a else ('УБИТ' if pb1a_kill else '?')} P-B1b {'✓' if pb1b else ('УБИТ' if pb1b_kill else '?')}", flush=True)

# ---------------- EXT-018 ----------------
if "e018" not in ck:
    volts = np.loadtxt(f"{TB}/quasi_static_experiments/control parameter/voltage_in_volt.txt")
    rows = []
    sE0 = None
    for k in range(1, 20):
        fp = f"{TB}/quasi_static_experiments/{k}.txt"
        if not os.path.exists(fp):
            rows.append(dict(k=k, skip="нет файла")); continue
        d = np.loadtxt(fp, encoding="latin-1")
        p = d[:, 1] if d.ndim == 2 else d
        t = (d[:, 0] - d[0, 0]) if d.ndim == 2 else np.arange(len(p)) * 1e-4
        dt = np.median(np.diff(t[:1000])); fs = 1.0 / dt
        seg = p[int(1.0 * fs): int(3.0 * fs)]
        if k == 1:
            sE0 = sE_of(seg)
        fire, dd = v2label(seg, sE0)
        rows.append(dict(k=k, V=float(volts[k - 1]), fire=bool(fire), z=dd["z"], T=dd["T"], A=dd["A"]))
        print(f"лестница #{k} V={volts[k-1]:.2f}: z={dd['z']:.1f} T={dd['T']:.0f} A={dd['A']:.1f} -> "
              f"{'ОСЦ' if fire else 'нет'} [{time.time()-t0:.0f}s]", flush=True)
    ok = [r for r in rows if "skip" not in r]
    fires = [r for r in ok if r["fire"]]
    Vstar = min((r["V"] for r in fires), default=None)
    islands = 0
    seq = sorted(ok, key=lambda r: r["V"])
    for i in range(1, len(seq) - 1):
        if seq[i - 1]["fire"] and not seq[i]["fire"] and seq[i + 1]["fire"]: islands += 1
    above = [r for r in seq if Vstar is not None and r["V"] >= Vstar]
    below = [r for r in seq if Vstar is None or r["V"] < Vstar]
    fr_above = sum(1 for r in above if r["fire"]) / len(above) if above else 0
    fr_below = sum(1 for r in below if r["fire"]) / len(below) if below else 0
    pb4a = Vstar is not None and fr_above >= 0.8 and fr_below <= 0.2 and islands < 2
    pb4a_kill = islands >= 2
    med_a = json.load(open("/home/claude/ver008b_results.json")).get("med_Vrel_a")
    pb4b = Vstar is not None and med_a is not None and Vstar < med_a - 0.32
    pb4b_kill = Vstar is not None and med_a is not None and Vstar >= med_a
    ck["e018"] = dict(rows=rows, Vstar=Vstar, islands=islands, fr_above=fr_above, fr_below=fr_below,
                      anchor_med=med_a, PB4a=bool(pb4a), PB4a_killed=bool(pb4a_kill),
                      PB4b=bool(pb4b), PB4b_killed=bool(pb4b_kill))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"E018: V*_qs={Vstar} | выше огней {fr_above:.2f}, ниже {fr_below:.2f}, островов {islands} | "
          f"якорь {med_a:.2f} -> P-B4a {'✓' if pb4a else ('УБИТ' if pb4a_kill else '?')} "
          f"P-B4b {'✓' if pb4b else ('УБИТ' if pb4b_kill else '?')}", flush=True)
print(f"[done {time.time()-t0:.0f}s]")
