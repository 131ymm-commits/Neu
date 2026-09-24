"""EXT-017 (Bonn 5 sets under v2 = z AND T) + EXT-020 (Delhi 3 stages). Per PREREG (frozen 2026-09-01)."""
import json, os, glob, time
import numpy as np
from scipy.io import loadmat

RNG = np.random.default_rng(424244)   # same RNG family as e005 machinery
CK = "/home/claude/ext017_020_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()

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
    return z, th, float(abs(d.sum()) / (2 * np.pi))

# ---------------- EXT-017 Bonn ----------------
if "e017" not in ck:
    res = {}
    for grp in ("A_Z", "B_O", "C_N", "D_F", "E_S"):
        files = sorted(glob.glob(f"/home/claude/EEG-Epilepsy-Datasets/bonn/{grp}/*.txt")) + \
                sorted(glob.glob(f"/home/claude/EEG-Epilepsy-Datasets/bonn/{grp}/*.TXT"))
        fires = 0
        for fp in files:
            x = np.loadtxt(fp)
            nf = 0
            for s0 in (0, 1024, 2048, 3072):
                w = wind_T(x[s0:s0 + 1024], 6)
                if w is None: continue
                z, th, T = w
                nf += bool(z >= th and T >= 2.0)
            fires += (nf >= 2)
        res[grp] = dict(n=len(files), fires=fires, rate=fires / max(len(files), 1))
        print(f"E017 {grp}: v2 {fires}/{len(files)} [{time.time()-t0:.0f}s]", flush=True)
    rE, rA, rB = res["E_S"]["rate"], res["A_Z"]["rate"], res["B_O"]["rate"]
    pb3a = rE >= 0.60; pb3a_kill = rE < 0.40
    pb3b = rA <= 0.10; pb3b_kill = rA >= 0.25
    pb3c = rB >= 0.30; pb3c_kill = rB < 0.10
    ck["e017"] = dict(res=res, PB3a=bool(pb3a), PB3a_killed=bool(pb3a_kill),
                      PB3b=bool(pb3b), PB3b_killed=bool(pb3b_kill),
                      PB3c=bool(pb3c), PB3c_killed=bool(pb3c_kill))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"E017: E={rE:.2f} (v1 0.77) A={rA:.2f} (v1 0.02) B={rB:.2f} (v1 0.49) C={res['C_N']['rate']:.2f} D={res['D_F']['rate']:.2f}", flush=True)

# ---------------- EXT-020 Delhi ----------------
if "e020" not in ck:
    res = {}
    base = "/home/claude/EEG-Epilepsy-Datasets/delhi/EEG Epilepsy Datasets"
    for stage in ("ictal", "interictal", "preictal"):
        files = sorted(glob.glob(f"{base}/{stage}/*.mat"))
        fires = 0; flat = 0
        for fp in files:
            m = loadmat(fp)
            key = [k for k in m if not k.startswith("__")][0]
            x = np.asarray(m[key], float).ravel()
            nf = 0
            for s0 in (0, 512):
                w = wind_T(x[s0:s0 + 512], 6)
                if w is None: flat += 1; continue
                z, th, T = w
                nf += bool(z >= th and T >= 2.0)
            fires += (nf >= 2)
        res[stage] = dict(n=len(files), fires=fires, rate=fires / max(len(files), 1), flat=flat)
        print(f"E020 {stage}: v2 {fires}/{len(files)} [{time.time()-t0:.0f}s]", flush=True)
    rI, rN = res["ictal"]["rate"], res["interictal"]["rate"]
    pb6a = rI >= 0.60; pb6a_kill = rI < 0.40
    pb6b = rN <= 0.20; pb6b_kill = rN >= 0.40
    ck["e020"] = dict(res=res, PB6a=bool(pb6a), PB6a_killed=bool(pb6a_kill),
                      PB6b=bool(pb6b), PB6b_killed=bool(pb6b_kill))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"E020: ictal={rI:.2f} interictal={rN:.2f} preictal={res['preictal']['rate']:.2f}", flush=True)
print(f"[done {time.time()-t0:.0f}s]")
