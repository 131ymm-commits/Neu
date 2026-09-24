"""PRE-004 — route-dependence of drift warning. Per PREREG (frozen 2026-08-24)."""
import json, os, sys, time
import numpy as np

SEED = 20260851
T_TOT = 600.0
REC_DT = 0.1
NSAMP = int(T_TOT / REC_DT)
W = 500          # window samples (50 t.u.)
STRIDE = 100     # 10 t.u.
LAG = 10         # 1 t.u.
CKPT = "/home/claude/pre004_ckpt.json"

# ---------- simulators: n_X trajectory under drifting parameter ----------
def sim_schlogl(par_fn, seed, ntraj):
    k1s, k4s = 5.75, 8.75
    SN1, Ww = 1.37154, 4.00578 - 1.37154
    V, XMAX, LAM = 20, 4.6, 275.0
    N = int(np.ceil(V * XMAX)); nvec = np.arange(N + 1); xv = nvec / V
    rng = np.random.default_rng(seed)
    fr0 = par_fn(0.0)
    k30 = SN1 + fr0 * Ww
    rts = np.roots([-1.0, k1s, -k4s, k30]); rts = np.sort(rts[np.isreal(rts)].real)
    st = np.full(ntraj, int(round(V * rts[0])), dtype=np.int64)
    steps = int(T_TOT * LAM)
    stride = int(REC_DT * LAM)
    rec = np.empty((ntraj, NSAMP))
    Wm = k4s * xv + xv**3; Wm[0] = 0.0
    for i in range(steps):
        fr = par_fn(i / LAM)
        k3 = SN1 + fr * Ww
        Wp = k3 + k1s * xv**2; Wp[-1] = 0.0
        u = rng.random(ntraj)
        pu, pd = Wp[st] / LAM, Wm[st] / LAM
        up = u < pu; dn = (~up) & (u < pu + pd)
        st += up.astype(np.int64) - dn.astype(np.int64)
        if (i + 1) % stride == 0:
            k = (i + 1) // stride - 1
            if k < NSAMP: rec[:, k] = st
    return rec

def sim_verhulst(par_fn, seed, ntraj):
    EPSV, KCAP, OM, DT = 0.1, 5.0, 50, 0.005
    rng = np.random.default_rng(seed)
    n = np.full(ntraj, int(round(EPSV * OM)), dtype=np.int64)
    steps = int(T_TOT / DT); stride = int(REC_DT / DT)
    rec = np.empty((ntraj, NSAMP))
    for i in range(steps):
        lam = par_fn(i * DT)
        birth = lam * n + EPSV * OM
        death = n + n.astype(float) ** 2 / (KCAP * OM)
        n = np.maximum(n + rng.poisson(birth * DT) - rng.poisson(death * DT), 0)
        if (i + 1) % stride == 0:
            k = (i + 1) // stride - 1
            if k < NSAMP: rec[:, k] = n
    return rec

def sim_bruss(par_fn, seed, ntraj):
    A_, OM, DT = 2.0, 500, 0.005
    rng = np.random.default_rng(seed)
    b0 = par_fn(0.0)
    nx = np.full(ntraj, int(round(A_ * OM)), dtype=np.int64)
    ny = np.full(ntraj, int(round(b0 / A_ * OM)), dtype=np.int64)
    steps = int(T_TOT / DT); stride = int(REC_DT / DT)
    rec = np.empty((ntraj, NSAMP))
    aW = A_ * OM
    for i in range(steps):
        b = par_fn(i * DT)
        nxf = nx.astype(float); nyf = ny.astype(float)
        r1 = rng.poisson(aW * DT, ntraj)
        r2 = rng.poisson(nxf * DT)
        r3 = rng.poisson(b * nxf * DT)
        r4 = rng.poisson(nxf * np.maximum(nxf - 1, 0) * nyf / OM**2 * DT)
        nx = np.maximum(nx + r1 - r2 - r3 + r4, 0)
        ny = np.maximum(ny + r3 - r4, 0)
        if (i + 1) % stride == 0:
            k = (i + 1) // stride - 1
            if k < NSAMP: rec[:, k] = nx
    return rec

SYS = {
    "fold": dict(sim=sim_schlogl, p0=0.30, p1=1.10, thr=1.00),
    "trans": dict(sim=sim_verhulst, p0=0.50, p1=1.50, thr=1.00),
    "hopf": dict(sim=sim_bruss, p0=4.00, p1=6.00, thr=5.00),
}

def indicators(traj):
    """Per window: (detrended variance, AC1 of residual at LAG). Window centers in samples."""
    out = []
    for s0 in range(0, NSAMP - W + 1, STRIDE):
        seg = traj[s0:s0 + W]
        x = np.arange(W)
        res = seg - np.polyval(np.polyfit(x, seg, 1), x)
        v = float(res.var())
        r0 = res[:-LAG]; r1 = res[LAG:]
        ac = float(np.corrcoef(r0, r1)[0, 1]) if res.std() > 0 else 0.0
        out.append((s0 + W // 2, v, ac))
    return out

def first_fire(ind, fv, fa):
    """First window index (2 consecutive) where var>=fv or ac>=fa. Returns sample center or None."""
    hitsv = [c for j, (c, v, a) in enumerate(ind[:-1])
             if v >= fv and ind[j + 1][1] >= fv]
    hitsa = [c for j, (c, v, a) in enumerate(ind[:-1])
             if a >= fa and ind[j + 1][2] >= fa]
    cands = ([("var", hitsv[0])] if hitsv else []) + ([("ac1", hitsa[0])] if hitsa else [])
    if not cands: return None, None
    which, c = min(cands, key=lambda t: t[1])
    return which, c

ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
t0 = time.time()
arg = sys.argv[1] if len(sys.argv) > 1 else "all"

for name, S in SYS.items():
    if arg != "all" and arg != name: continue
    if name in ck: continue
    p0, p1, thr = S["p0"], S["p1"], S["thr"]
    drift = lambda t: p0 + (p1 - p0) * min(t / T_TOT, 1.0)
    const = lambda t: p0
    base = S["sim"](const, SEED + hash(name) % 1000, 5)
    ctrl = S["sim"](const, SEED + hash(name) % 1000 + 77, 5)
    drf = S["sim"](drift, SEED + hash(name) % 1000 + 154, 5)
    # floors from base
    fv = fa = -np.inf
    for r in range(5):
        for (_, v, a) in indicators(base[r]):
            fv = max(fv, v); fa = max(fa, a)
    fv *= 2.5; fa = min(2.5 * fa, 0.999)
    fires, leads, whichs = 0, [], []
    for r in range(5):
        w_, c = first_fire(indicators(drf[r]), fv, fa)
        if c is not None:
            par = drift(c * REC_DT)
            if par < thr:
                fires += 1
                leads.append((thr - par) / (p1 - p0))
                whichs.append(w_)
    cfire = 0
    for r in range(5):
        w_, c = first_fire(indicators(ctrl[r]), fv, fa)
        if c is not None: cfire += 1
    ck[name] = dict(floor_var=fv, floor_ac=fa, fires=fires, leads=leads, which=whichs,
                    ctrl_fires=cfire)
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"{name}: полы var={fv:.3g} ac={fa:.3f} | до-пороговых {fires}/5 "
          f"(lead={[round(l,3) for l in leads]}, {whichs}) | контроль {cfire}/5 "
          f"[{time.time()-t0:.0f}s]", flush=True)

if all(n in ck for n in SYS):
    f_f, f_t, f_h = ck["fold"]["fires"], ck["trans"]["fires"], ck["hopf"]["fires"]
    pv1 = f_f >= 4; pv1_kill = f_f <= 2
    pv2 = "a" if f_t >= 4 else ("b" if f_t <= 1 else "не установлен")
    pv3a = f_h >= 4; pv3a_kill = f_h <= 2
    ml_f = float(np.median(ck["fold"]["leads"])) if ck["fold"]["leads"] else None
    ml_h = float(np.median(ck["hopf"]["leads"])) if ck["hopf"]["leads"] else None
    pv3b = (ml_f is not None and ml_h is not None and ml_h >= 3 * ml_f)
    pv4_bad = [n for n in SYS if ck[n]["ctrl_fires"] >= 2]
    pv4 = len(pv4_bad) == 0
    ck["verdicts"] = dict(PV1=bool(pv1), PV1_killed=bool(pv1_kill), PV2=pv2,
                          PV3a=bool(pv3a), PV3a_killed=bool(pv3a_kill), PV3b=bool(pv3b),
                          ml_fold=ml_f, ml_hopf=ml_h, PV4=bool(pv4), pv4_bad=pv4_bad)
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"\nP-V1 (фолд): {f_f}/5 -> {'ПОДТВЕРЖДЁН' if pv1 else ('УБИТ' if pv1_kill else 'не установлен')}")
    print(f"P-V2 (транскритика): {f_t}/5 -> ветвь ({pv2})")
    print(f"P-V3a (Хопф): {f_h}/5 -> {'ПОДТВЕРЖДЁН' if pv3a else ('УБИТ' if pv3a_kill else 'не установлен')}; "
          f"P-V3b: lead {ml_h} против {ml_f} (×3: {pv3b})")
    print(f"P-V4 (контроли): {'ПОДТВЕРЖДЁН' if pv4 else 'УБИТ: ' + str(pv4_bad)} "
          f"({[ck[n]['ctrl_fires'] for n in SYS]})")
print(f"[{time.time()-t0:.0f}s]")
