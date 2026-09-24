"""LEV-001 main run — everything per PREREG.md (frozen). Seed 20260823."""
import numpy as np, json, time
from scipy.linalg import eigh_tridiagonal
from scipy.signal import find_peaks
from scipy.stats import spearmanr

k1, k4 = 5.75, 8.75
SN1, SN2 = 1.37154, 4.00578
Wwin = SN2 - SN1
XMAX, LAM = 4.6, 275.0
T_TRAJ, STRIDE = 400.0, 16
NSTEP = int(T_TRAJ * LAM)              # 110000
NSAMP = NSTEP // STRIDE                # 6875
BURN = int(0.05 * NSAMP)
DT_REC = STRIDE / LAM
NTRAJ = 320
BUDGETS = {"B1": 20, "B2": 80, "B3": 320}
LAGS = [32, 64, 128, 256, 512]
LAG_MAIN = 256
PLATEAU_LAGS = [128, 256, 512]
BINW = 2
MINVIS = 50
RSTAR = {20: 5.5, 30: 7.5}
FR_GRID = np.round(np.linspace(-0.08, 0.85, 17), 4)
FR_DEG = [(0.4 - SN1) / Wwin, (0.7 - SN1) / Wwin, (1.0 - SN1) / Wwin]
SURR_FR = [0.152, 0.501, 0.850]        # nearest grid points used
rng_master = np.random.default_rng(20260823)

def build(V, k3):
    N = int(np.ceil(V * XMAX))
    x = np.arange(N + 1) / V
    Wp = k3 + k1 * x**2; Wm = k4 * x + x**3
    Wp[-1] = 0.0; Wm[0] = 0.0
    return N, Wp, Wm

def exact_all(V, k3):
    N, Wp, Wm = build(V, k3)
    lg = np.concatenate([[0.0], np.cumsum(np.log(np.where(Wp[:-1] > 0, Wp[:-1], 1e-300))
                                          - np.log(np.where(Wm[1:] > 0, Wm[1:], 1e-300)))])
    lg -= lg.max(); pi = np.exp(lg); pi /= pi.sum()
    d = -(Wp + Wm); off = np.sqrt(Wp[:-1] * Wm[1:])
    ev = np.sort(eigh_tridiagonal(d, off, eigvals_only=True))[::-1]
    t = 1.0 / (-ev[1:4])
    r = np.roots([-1.0, k1, -k4, k3]); r = np.sort(r[np.isreal(r)].real); r = r[r >= -1e-9]
    out = dict(t2=t[0], t3=t[1], R=t[0] / t[1], roots=list(r))
    if len(r) == 3:
        nl, nh = int(round(V * r[0])), int(round(V * r[2]))
        cs = np.cumsum(pi); j = np.arange(nl, nh)
        out["T_lh"] = float(np.sum(cs[j] / (Wp[j] * pi[j])))
        csr = np.cumsum(pi[::-1])[::-1]; j2 = np.arange(nl + 1, nh + 1)
        out["T_hl"] = float(np.sum(csr[j2] / (Wm[j2] * pi[j2])))
    sm = np.convolve(pi, np.ones(3) / 3, mode='same')
    pk, _ = find_peaks(sm, prominence=0.05 * sm.max())
    out["pi_peaks"] = int(len(pk))
    out["n_start"] = int(round(V * r[0]))
    return out, pi

def simulate(V, k3, seed):
    N, Wp, Wm = build(V, k3)
    pu, pd = Wp / LAM, Wm / LAM
    rng = np.random.default_rng(seed)
    ex, _ = exact_all(V, k3)
    st = np.full(NTRAJ, ex["n_start"], dtype=np.int64)
    rec = np.empty((NTRAJ, NSAMP), dtype=np.int16)
    for i in range(NSTEP):
        u = rng.random(NTRAJ)
        up = u < pu[st]
        dn = (~up) & (u < pu[st] + pd[st])
        st += up.astype(np.int64) - dn.astype(np.int64)
        if (i + 1) % STRIDE == 0:
            rec[:, (i + 1) // STRIDE - 1] = st
    return rec[:, BURN:], N

def spectral_R(data, N, lags=LAGS, min_vis=MINVIS, per_traj_main=False):
    """data: (ntraj, T) int16. Returns dict lag->(t2,t3) + per-traj counts at LAG_MAIN."""
    nb = N // BINW + 1
    b = (data.astype(np.int32) // BINW)
    res = {}
    Cmain_per = None
    for lag in lags:
        a0 = b[:, :-lag].ravel(); a1 = b[:, lag:].ravel()
        C = np.bincount(a0 * nb + a1, minlength=nb * nb).reshape(nb, nb).astype(np.float64)
        C = C + C.T
        vis = C.sum(1)
        keep = vis >= min_vis
        if keep.sum() < 3:
            res[lag] = (np.nan, np.nan); continue
        Ck = C[np.ix_(keep, keep)]
        s = Ck.sum(1)
        A = Ck / np.sqrt(np.outer(s, s))
        evv = np.sort(np.linalg.eigvalsh((A + A.T) / 2))[::-1]
        lam2 = evv[1] if len(evv) > 1 else np.nan
        lam3 = evv[2] if len(evv) > 2 else np.nan
        tau = lag * DT_REC
        t2 = -tau / np.log(lam2) if (lam2 is not np.nan and 0 < lam2 < 1) else np.nan
        t3 = -tau / np.log(lam3) if (lam3 is not np.nan and 0 < lam3 < 1) else np.nan
        res[lag] = (t2, t3)
        if lag == LAG_MAIN and per_traj_main:
            Cmain_per = np.zeros((data.shape[0], nb, nb), dtype=np.int32)
            for j in range(data.shape[0]):
                Cj = np.bincount(b[j, :-lag] * nb + b[j, lag:], minlength=nb * nb).reshape(nb, nb)
                Cmain_per[j] = Cj
    return res, Cmain_per, nb

def R_from_counts(C, min_vis=MINVIS, tau=LAG_MAIN * DT_REC):
    C = C + C.T
    keep = C.sum(1) >= min_vis
    if keep.sum() < 3: return np.nan, np.nan, np.nan
    Ck = C[np.ix_(keep, keep)].astype(np.float64)
    s = Ck.sum(1)
    A = Ck / np.sqrt(np.outer(s, s))
    evv = np.sort(np.linalg.eigvalsh((A + A.T) / 2))[::-1]
    if len(evv) < 3 or not (0 < evv[1] < 1) or not (0 < evv[2] < 1):
        return np.nan, np.nan, np.nan
    t2 = -tau / np.log(evv[1]); t3 = -tau / np.log(evv[2])
    return t2 / t3, t2, t3

def bimodal(data, N):
    h = np.bincount((data.astype(np.int32) // BINW).ravel(), minlength=N // BINW + 1).astype(float)
    sm = np.convolve(h, np.ones(3) / 3, mode='same')
    pk, props = find_peaks(sm, prominence=0.05 * sm.max())
    if len(pk) < 2: return False, len(pk)
    order = np.argsort(sm[pk])[::-1]
    second = pk[order[1]]
    mass = h[max(0, second - 2): second + 3].sum()
    return bool(mass >= 100), int(len(pk))

t0 = time.time()
results = {}
for V in (20, 30):
    results[V] = {"grid": [], "deg": [], "surr": []}
    # window grid
    for gi, fr in enumerate(FR_GRID):
        k3 = SN1 + fr * Wwin
        ex, _ = exact_all(V, k3)
        rec, N = simulate(V, k3, seed=int(1e6 * V + gi))
        entry = dict(fr=float(fr), k3=float(k3), exact=ex, budgets={})
        for bn, nt in BUDGETS.items():
            sub = rec[:nt]
            res, Cper, nb = spectral_R(sub, N, per_traj_main=True)
            t2m, t3m = res[LAG_MAIN]
            Rm = t2m / t3m if (t2m == t2m and t3m == t3m) else np.nan
            t2s = [res[l][0] for l in PLATEAU_LAGS]
            plateau = (np.nanmax(t2s) - np.nanmin(t2s)) / np.nanmean(t2s) < 0.20 if not np.any(np.isnan(t2s)) else False
            # jackknife
            jr = []
            if Cper is not None:
                Ctot = Cper.sum(0)
                for j in range(nt):
                    Rj, _, _ = R_from_counts(Ctot - Cper[j])
                    jr.append(Rj)
            jr = np.array(jr, dtype=float)
            j16 = float(np.nanpercentile(jr, 16)) if len(jr) else np.nan
            j84 = float(np.nanpercentile(jr, 84)) if len(jr) else np.nan
            bi, npk = bimodal(sub, N)
            entry["budgets"][bn] = dict(R=float(Rm) if Rm == Rm else None,
                                        t2=float(t2m) if t2m == t2m else None,
                                        t3=float(t3m) if t3m == t3m else None,
                                        plateau=bool(plateau), j16=j16, j84=j84,
                                        bimodal=bool(bi), n_peaks=npk)
        results[V]["grid"].append(entry)
        print(f"V={V} fr={fr:+.3f} " + " ".join(
            f"{bn}:R={e['R'] and round(e['R'],2)} pl={int(e['plateau'])} bi={int(e['bimodal'])}"
            for bn, e in entry["budgets"].items()), flush=True)
    # degenerate controls
    for di, k3 in enumerate([0.4, 0.7, 1.0]):
        ex, _ = exact_all(V, k3)
        rec, N = simulate(V, k3, seed=int(2e6 * V + di))
        entry = dict(k3=k3, exact=ex, budgets={})
        for bn, nt in BUDGETS.items():
            res, _, _ = spectral_R(rec[:nt], N)
            t2m, t3m = res[LAG_MAIN]
            Rm = t2m / t3m if (t2m == t2m and t3m == t3m) else np.nan
            bi, npk = bimodal(rec[:nt], N)
            entry["budgets"][bn] = dict(R=float(Rm) if Rm == Rm else None, bimodal=bool(bi))
        results[V]["deg"].append(entry)
        print(f"V={V} DEG k3={k3} " + " ".join(f"{bn}:R={e['R'] and round(e['R'],2)}"
              for bn, e in entry["budgets"].items()), flush=True)
    # surrogates (B2)
    for fr in SURR_FR:
        gi = int(np.argmin(np.abs(FR_GRID - fr)))
        k3 = SN1 + FR_GRID[gi] * Wwin
        rec, N = simulate(V, k3, seed=int(3e6 * V + gi))
        sub = rec[:BUDGETS["B2"]].copy()
        rs = np.random.default_rng(777)
        for j in range(sub.shape[0]):
            rs.shuffle(sub[j])
        res, _, _ = spectral_R(sub, N)
        t2m, t3m = res[LAG_MAIN]
        Rm = t2m / t3m if (t2m == t2m and t3m == t3m) else np.nan
        bi, _ = bimodal(sub, N)
        results[V]["surr"].append(dict(fr=float(FR_GRID[gi]),
                                       R=float(Rm) if Rm == Rm else None,
                                       t2=float(t2m) if t2m == t2m else None,
                                       bimodal=bool(bi)))
        print(f"V={V} SURR fr={FR_GRID[gi]:+.3f} R={Rm if Rm==Rm else None} t2={t2m if t2m==t2m else None} bi={int(bi)}", flush=True)

# budget convergence curve at chosen point fr=0.618
CONV = {}
for V in (20, 30):
    gi = int(np.argmin(np.abs(FR_GRID - 0.618)))
    k3 = SN1 + FR_GRID[gi] * Wwin
    rec, N = simulate(V, k3, seed=int(4e6 * V))
    pts = []
    for nt in [20, 40, 80, 160, 320]:
        res, _, _ = spectral_R(rec[:nt], N)
        t2m, t3m = res[LAG_MAIN]
        pts.append(dict(n=nt, R=float(t2m / t3m) if (t2m == t2m and t3m == t3m) else None))
    CONV[V] = dict(fr=float(FR_GRID[gi]), pts=pts)
    print(f"V={V} CONV fr={FR_GRID[gi]} " + " ".join(f"{p['n']}:{p['R'] and round(p['R'],2)}" for p in pts), flush=True)

json.dump(dict(results={str(k): v for k, v in results.items()}, conv={str(k): v for k, v in CONV.items()},
               meta=dict(RSTAR=RSTAR, FR_GRID=FR_GRID.tolist())),
          open("/home/claude/lev001_results.json", "w"), default=float)
print(f"\nDONE in {time.time()-t0:.0f}s -> lev001_results.json")
