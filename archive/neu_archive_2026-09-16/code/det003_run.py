"""DET-003 run — per PREREG. Non-symmetrized estimator, complex eigenvalues, angle."""
import json, time, numpy as np

SEED = 20260825
SIGMA = 0.02
T_STEPS = 3000
BURN = int(0.05 * T_STEPS)
NTRAJ = 320
BUDGETS = {"B1": 20, "B2": 80, "B3": 320}
NB = 40
MINVIS = 50
LAGS = [1, 2, 3, 4, 8]
LAG_MAIN = 4
PLATEAU = [2, 4, 8]
R_DEG = [2.60, 2.75, 2.90]
R_WIN = list(np.round(np.linspace(2.96, 3.40, 12), 4))

def simulate(r, ntraj, seed):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0.2, 0.8, ntraj)
    rec = np.empty((ntraj, T_STEPS), dtype=np.int8)
    for t in range(T_STEPS):
        x = np.clip(r * x * (1 - x) + SIGMA * rng.standard_normal(ntraj), 0.0, 1.0)
        rec[:, t] = np.minimum((x * NB).astype(np.int32), NB - 1)
    return rec[:, BURN:]

def eig_from_counts(C):
    keep = C.sum(1) >= MINVIS
    if keep.sum() < 3: return None
    Ck = C[np.ix_(keep, keep)].astype(np.float64)
    T = Ck / Ck.sum(1, keepdims=True)
    ev = np.linalg.eigvals(T)
    ev = ev[np.argsort(-np.abs(ev))]
    return ev

def counts(data, lag, per_traj=False):
    a0 = data[:, :-lag].astype(np.int32).ravel()
    a1 = data[:, lag:].astype(np.int32).ravel()
    C = np.bincount(a0 * NB + a1, minlength=NB * NB).reshape(NB, NB).astype(np.float64)
    Cp = None
    if per_traj:
        Cp = np.zeros((data.shape[0], NB, NB), dtype=np.int32)
        for j in range(data.shape[0]):
            Cp[j] = np.bincount(data[j, :-lag].astype(np.int32) * NB + data[j, lag:],
                                minlength=NB * NB).reshape(NB, NB)
    return C, Cp

def analyze(data):
    res = {}
    for lag in LAGS:
        C, _ = counts(data, lag)
        ev = eig_from_counts(C)
        if ev is None or len(ev) < 3:
            res[lag] = None; continue
        l2, l3 = ev[1], ev[2]
        t2 = -lag / np.log(np.abs(l2)) if 0 < np.abs(l2) < 1 else np.nan
        t3 = -lag / np.log(np.abs(l3)) if 0 < np.abs(l3) < 1 else np.nan
        res[lag] = dict(abs2=float(np.abs(l2)), re2=float(np.real(l2)),
                        th=float(np.angle(l2)), abs3=float(np.abs(l3)),
                        t2=float(t2), t3=float(t3))
    m = res[LAG_MAIN]
    Rc = m["t2"] / m["t3"] if m and m["t2"] == m["t2"] and m["t3"] == m["t3"] else np.nan
    t2s = [res[l]["t2"] for l in PLATEAU if res[l]]
    plateau = len(t2s) == 3 and not np.any(np.isnan(t2s)) and \
              (max(t2s) - min(t2s)) / np.mean(t2s) < 0.20
    sign_ok = (res[1] and res[3] and res[2] and res[4] and
               res[1]["re2"] < 0 and res[3]["re2"] < 0 and
               res[2]["re2"] > 0 and res[4]["re2"] > 0)
    theta1 = res[1]["th"] if res[1] else np.nan
    return dict(Rc=float(Rc) if Rc == Rc else None, plateau=bool(plateau),
                sign_alt=bool(sign_ok), theta1=float(theta1), lags=res)

def jack(data):
    _, Cp4 = counts(data, LAG_MAIN, per_traj=True)
    _, Cp1 = counts(data, 1, per_traj=True)
    C4 = Cp4.sum(0); C1 = Cp1.sum(0)
    Rcs, ths = [], []
    for j in range(data.shape[0]):
        ev4 = eig_from_counts((C4 - Cp4[j]).astype(np.float64))
        ev1 = eig_from_counts((C1 - Cp1[j]).astype(np.float64))
        if ev4 is not None and len(ev4) > 2 and 0 < np.abs(ev4[1]) < 1 and 0 < np.abs(ev4[2]) < 1:
            t2 = -LAG_MAIN / np.log(np.abs(ev4[1])); t3 = -LAG_MAIN / np.log(np.abs(ev4[2]))
            Rcs.append(t2 / t3)
        if ev1 is not None and len(ev1) > 1:
            ths.append(np.angle(ev1[1]))
    Rcs = np.array(Rcs); ths = np.array(ths)
    j16 = float(np.nanpercentile(Rcs, 16)) if len(Rcs) else np.nan
    Rbar = np.abs(np.mean(np.exp(1j * ths))) if len(ths) else np.nan
    circ_sd = float(np.sqrt(max(-2 * np.log(Rbar), 0))) if Rbar == Rbar and Rbar > 0 else np.nan
    th_mean = float(np.angle(np.mean(np.exp(1j * ths)))) if len(ths) else np.nan
    return j16, circ_sd, th_mean

t0 = time.time()
out = {"deg": {}, "win": {}, "surr": [], "conv": None, "fold": {}}

# Stage A: degenerate -> freeze R*
for r in R_DEG:
    rec = simulate(r, NTRAJ, seed=SEED + int(r * 100))
    e = {}
    for bn, nt in BUDGETS.items():
        a = analyze(rec[:nt])
        e[bn] = a
    out["deg"][r] = e
    print(f"DEG r={r}: " + " ".join(f"{bn}:Rc={e[bn]['Rc'] and round(e[bn]['Rc'],2)} "
          f"pl={int(e[bn]['plateau'])}" for bn in BUDGETS), flush=True)
maxdeg = max(e["B3"]["Rc"] or 0 for e in out["deg"].values())
RSTAR = max(5.0, 2.5 * maxdeg)
out["RSTAR"] = RSTAR
print(f"R* = {RSTAR:.2f} (заморожено; max deg B3 = {maxdeg:.2f})", flush=True)

# Stage B: window
for r in R_WIN:
    rec = simulate(r, NTRAJ, seed=SEED + int(r * 1000))
    e = {}
    for bn, nt in BUDGETS.items():
        a = analyze(rec[:nt])
        j16, csd, thm = jack(rec[:nt])
        a["j16"] = j16; a["th_sd"] = csd; a["th_mean"] = thm
        e[bn] = a
    out["win"][r] = e
    b3 = e["B3"]
    print(f"WIN r={r}: B3 Rc={b3['Rc'] and round(b3['Rc'],1)} pl={int(b3['plateau'])} "
          f"j16={b3['j16'] and round(b3['j16'],1)} th/pi={b3['theta1']/np.pi:+.2f} "
          f"sd={b3['th_sd'] and round(b3['th_sd'],2)} alt={int(b3['sign_alt'])} | "
          f"B1 Rc={e['B1']['Rc'] and round(e['B1']['Rc'],1)}", flush=True)
    if abs(r - 3.16) < 0.03:
        pts = []
        for nt in (20, 40, 80, 160, 320):
            a = analyze(rec[:nt])
            pts.append(dict(n=nt, Rc=a["Rc"]))
        out["conv"] = dict(r=r, pts=pts)

# surrogates (B2)
for r in (2.60, 3.10, 3.30):
    rec = simulate(r, BUDGETS["B2"], seed=SEED + 777 + int(r * 10))
    sub = rec.copy()
    rs = np.random.default_rng(777)
    for j in range(sub.shape[0]):
        rs.shuffle(sub[j])
    a = analyze(sub)
    out["surr"].append(dict(r=r, Rc=a["Rc"], plateau=a["plateau"]))
    print(f"SURR r={r}: Rc={a['Rc'] and round(a['Rc'],2)} pl={int(a['plateau'])}", flush=True)

# fold comparator: Schlogl chain (LEV-001 system), non-symmetrized, lags in recorded units
k1, k4 = 5.75, 8.75
SN1, Wwin = 1.37154, 4.00578 - 1.37154
V, XMAX, LAM = 20, 4.6, 275.0
def schlogl_rec(fr, ntraj, seed):
    k3 = SN1 + fr * Wwin
    N = int(np.ceil(V * XMAX))
    n = np.arange(N + 1)
    x = n / V
    Wp = k3 + k1 * x**2; Wm = k4 * x + x**3
    Wp[-1] = 0.0; Wm[0] = 0.0
    pu, pd = Wp / LAM, Wm / LAM
    rng = np.random.default_rng(seed)
    r = np.roots([-1.0, k1, -k4, k3]); r = np.sort(r[np.isreal(r)].real)
    st = np.full(ntraj, int(round(V * r[0])), dtype=np.int64)
    STEPS, STRIDE = 110000, 16
    nsamp = STEPS // STRIDE
    rec = np.empty((ntraj, nsamp), dtype=np.int16)
    for i in range(STEPS):
        u = rng.random(ntraj)
        up = u < pu[st]; dn = (~up) & (u < pu[st] + pd[st])
        st += up.astype(np.int64) - dn.astype(np.int64)
        if (i + 1) % STRIDE == 0:
            rec[:, (i + 1) // STRIDE - 1] = st
    return rec[:, int(0.05 * nsamp):], N

for fr in (0.618, 0.734, 0.850):
    rec, N = schlogl_rec(fr, BUDGETS["B2"], seed=SEED + int(fr * 1000))
    b = np.clip(rec.astype(np.int32) // 2, 0, N // 2)
    nb = N // 2 + 1
    res = {}
    for lag in (1, 2, 3, 4):
        a0 = b[:, :-lag].ravel(); a1 = b[:, lag:].ravel()
        C = np.bincount(a0 * nb + a1, minlength=nb * nb).reshape(nb, nb).astype(np.float64)
        keep = C.sum(1) >= MINVIS
        Ck = C[np.ix_(keep, keep)]
        T = Ck / Ck.sum(1, keepdims=True)
        ev = np.linalg.eigvals(T); ev = ev[np.argsort(-np.abs(ev))]
        res[lag] = dict(re2=float(np.real(ev[1])), th=float(np.angle(ev[1])),
                        abs2=float(np.abs(ev[1])))
    out["fold"][fr] = res
    print(f"FOLD fr={fr}: th1/pi={res[1]['th']/np.pi:+.3f} "
          f"re2 lags={[round(res[l]['re2'],3) for l in (1,2,3,4)]}", flush=True)

json.dump(out, open("/home/claude/det003_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det003_results.json")
