"""ORD-001 — cooperativity as switch of birth type. Per PREREG (frozen 2026-08-24)."""
import json, time
import numpy as np

exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])

M = 10
SEED = 20260845
GRAPHS = [5201, 5202, 5203, 5204, 5205]
KAPPAS = np.linspace(1.0, 20.0, 200)
RELAX = 20000
N_HOT = 40
T_STOCH = 100.0
STEPS_ST = int(T_STOCH / DT)

def h2(n): return n * n / (16.0 + n * n)
def h1(n): return n / (4.0 + n)

def mf_relax(A, kap, hfun, n0, steps=RELAX):
    n = n0.copy()
    for _ in range(steps):
        n += 0.01 * (EPS + kap * (A.T @ hfun(n)) - n)
    return n

def sweep(A, hfun):
    up, dn = [], []
    n = np.full(M, EPS)
    for k in KAPPAS:
        n = mf_relax(A, k, hfun, n)
        up.append(n.sum())
    n = n.copy()
    for k in KAPPAS[::-1]:
        n = mf_relax(A, k, hfun, n)
        dn.append(n.sum())
    dn = dn[::-1]
    up, dn = np.array(up), np.array(dn)
    rng_mass = max(up.max(), dn.max()) - min(up.min(), dn.min())
    A_loop = float(np.sum(np.abs(up - dn)) * (KAPPAS[1] - KAPPAS[0]) /
                   (rng_mass * (KAPPAS[-1] - KAPPAS[0]) + 1e-12))
    return up, dn, A_loop

def two_start_mf(A, kap, hfun):
    lo = mf_relax(A, kap, hfun, np.full(M, EPS), 60000)
    hi = mf_relax(A, kap, hfun, np.full(M, 12.0), 60000)
    return lo.sum(), hi.sum(), bool(abs(hi.sum() - lo.sum()) > 0.5)

def sim(A, kap, hfun, seed, init, nsteps=STEPS_ST, rec=100):
    rng = np.random.default_rng(seed)
    n = rng.poisson(np.maximum(init, 0), size=(N_HOT, M)).astype(float)
    pdeath = 1 - np.exp(-DT)
    Af = A.astype(float)
    tot = []
    for s in range(nsteps):
        b = EPS + kap * (hfun(n) @ Af)
        n = np.clip(n + rng.poisson(b * DT) - rng.binomial(n.astype(np.int64), pdeath), 0, NCAP)
        if (s + 1) % rec == 0:
            tot.append(n.sum(1).copy())
    return np.array(tot)  # (nsamp, N_HOT)

def _runs(sym, mode):
    idx = np.flatnonzero(sym)
    if idx.size == 0: return np.empty(0, dtype=int)
    if idx.size == 1: return np.array([1])
    adj = np.diff(idx) == 1
    ok = (sym[idx[1:]] == -sym[idx[:-1]]) if mode == "alt" else (sym[idx[1:]] == sym[idx[:-1]])
    brk = ~(adj & ok)
    bounds = np.r_[0, np.flatnonzero(brk) + 1, idx.size]
    return np.diff(bounds)

def cert_alt_rot(traj):
    """traj: (nsamp, N_HOT) total-mass; per-trajectory series."""
    X = traj.T  # (N_HOT, nsamp)
    alt = np.concatenate([_runs(np.sign(np.diff(row)).astype(np.int8), "alt") for row in X])
    L_alt = float(np.median(alt))
    u = X[:, 1:] - X.mean()
    v = X[:, :-1] - X.mean()
    phi = np.arctan2(v, u)
    dphi = np.angle(np.exp(1j * np.diff(phi, axis=1)))
    rot = np.concatenate([_runs(np.sign(row).astype(np.int8), "const") for row in dphi])
    L_rot = float(np.median(rot))
    return L_alt, L_rot

t0 = time.time()
out = {}
for sg in GRAPHS:
    edges = edges_seq(M, sg)
    Kc = k_cycle(edges, M)
    A = adj_at(edges, M, Kc)
    Ad = adj_at(edges, M, Kc, dag=True)
    e = {"Kc": Kc, "h": {}}
    for hname, hfun in (("h2", h2), ("h1", h1)):
        up, dn, A_loop = sweep(A, hfun)
        # bistable window (mf two-start over kappa grid, coarse: every 10th)
        split_ks = []
        for k in KAPPAS[::10]:
            lo, hi, sp = two_start_mf(A, k, hfun)
            if sp: split_ks.append(float(k))
        splitness = len(split_ks) > 0
        # smoothness for P-O4 (h1): max relative jump on up-branch
        jumps = np.abs(np.diff(up)) / (np.abs(up[:-1]) + 1e-9)
        e["h"][hname] = dict(A_loop=A_loop, split=bool(splitness),
                             split_lo=(min(split_ks) if split_ks else None),
                             split_hi=(max(split_ks) if split_ks else None),
                             max_jump=float(np.max(jumps)))
        print(f"g{sg} {hname}: A_loop={A_loop:.3f} split={splitness} "
              f"window=[{min(split_ks) if split_ks else '-'}, {max(split_ks) if split_ks else '-'}] "
              f"max_jump={np.max(jumps):.2f} [{time.time()-t0:.0f}s]", flush=True)
    # kappa_mid from h2 window (fallback: middle of sweep)
    w = e["h"]["h2"]
    kmid = 0.5 * (w["split_lo"] + w["split_hi"]) if w["split"] else 10.0
    e["kappa_mid"] = kmid
    # stochastic checks at kmid
    for hname, hfun in (("h2", h2), ("h1", h1)):
        lo_mf = mf_relax(A, kmid, hfun, np.full(M, EPS), 60000)
        hi_mf = mf_relax(A, kmid, hfun, np.full(M, 12.0), 60000)
        dl, ht = lo_mf.sum(), hi_mf.sum()
        hi_thr = dl + 0.6 * (ht - dl) if ht - dl >= 2 else dl + 6.0
        dark_t = sim(A, kmid, hfun, SEED + sg * 10 + 1, lo_mf)
        hot_t = sim(A, kmid, hfun, SEED + sg * 10 + 2, hi_mf if ht - dl >= 2 else np.full(M, 12.0))
        # C1: waiting/crossing on dark starts
    # (C1 computed for h2 only per prereg P-O3)
    lo_mf2 = mf_relax(A, kmid, h2, np.full(M, EPS), 60000)
    hi_mf2 = mf_relax(A, kmid, h2, np.full(M, 12.0), 60000)
    dl, ht = lo_mf2.sum(), hi_mf2.sum()
    hi_thr = dl + 0.6 * (ht - dl) if ht - dl >= 2 else dl + 6.0
    de_thr, he_thr = dl + 0.2 * (ht - dl), dl + 0.8 * (ht - dl)
    dark2 = sim(A, kmid, h2, SEED + sg * 10 + 3, lo_mf2, nsteps=40000)  # T=400 budget
    tw, tc = [], []
    for j in range(N_HOT):
        tr = dark2[:, j]
        hot_i = np.flatnonzero(tr >= he_thr)
        if hot_i.size == 0: continue
        hI = hot_i[0]
        dk = np.flatnonzero(tr[:hI] <= de_thr)
        d0 = dk[-1] if dk.size else 0
        tw.append(hI); tc.append(hI - d0)
    npass = len(tw)
    S = float(np.median(tw) / np.median(tc)) if npass else np.nan
    c1 = bool(npass >= 20 and S == S and S >= 3.0)
    hot2 = sim(A, kmid, h2, SEED + sg * 10 + 4, hi_mf2)
    p_hot = float((hot2[-1] > hi_thr).mean())
    lo_d = mf_relax(Ad, kmid, h2, np.full(M, EPS), 60000)
    hotd = sim(Ad, kmid, h2, SEED + sg * 10 + 5, np.full(M, 12.0))
    hi_d = lo_d.sum() + 0.6 * (ht - dl) if ht - dl >= 2 else lo_d.sum() + 6.0
    p_dag = float((hotd[-1] > hi_d).mean())
    c2 = bool(p_hot >= 0.15 and p_hot - p_dag >= 0.10)
    e["h2_cert"] = dict(npass=npass, S=S, C1=c1, p_hot=p_hot, p_dag=p_dag, C2=c2,
                        fires=bool(c1 and c2))
    # trio blindness at h1: stationary trajectories at kmid and 1.5*kmid
    blind = {}
    lo1 = mf_relax(A, kmid, h1, np.full(M, EPS), 60000)
    hi1 = mf_relax(A, kmid, h1, np.full(M, 12.0), 60000)
    struct_silent = abs(hi1.sum() - lo1.sum()) <= 0.5
    for kf, kk in (("k1.0", kmid), ("k1.5", 1.5 * kmid)):
        st = sim(A, kk, h1, SEED + sg * 10 + 6 + int(kf == "k1.5"), mf_relax(A, kk, h1, np.full(M, EPS), 60000))
        L_alt, L_rot = cert_alt_rot(st)
        blind[kf] = dict(L_alt=L_alt, L_rot=L_rot)
    e["h1_trio"] = dict(struct_silent=bool(struct_silent), **blind)
    any_fire_h1 = (not struct_silent) or any(
        blind[kf]["L_alt"] >= 8 or blind[kf]["L_rot"] >= 8 for kf in blind)
    e["h1_any_fire"] = bool(any_fire_h1)
    out[sg] = e
    print(f"g{sg}: kmid={kmid:.1f} | h2-cert: пасс={npass} S={S:.1f} C1={int(c1)} "
          f"p={p_hot:.2f}/{p_dag:.2f} C2={int(c2)} fires={int(c1 and c2)} | "
          f"h1: struct_silent={struct_silent} L_alt/rot={[(blind[k]['L_alt'], blind[k]['L_rot']) for k in blind]} "
          f"[{time.time()-t0:.0f}s]", flush=True)

# ===== verdicts =====
h2A = [out[g]["h"]["h2"]["A_loop"] for g in GRAPHS]
h1A = [out[g]["h"]["h1"]["A_loop"] for g in GRAPHS]
h2sp = [out[g]["h"]["h2"]["split"] for g in GRAPHS]
h1sp = [out[g]["h"]["h1"]["split"] for g in GRAPHS]
po1 = (sum(1 for a, s in zip(h2A, h2sp) if a >= 0.2 and s) >= 4 and
       all(a <= 0.05 for a in h1A) and not any(h1sp))
po1_kill = (sum(1 for a, s in zip(h1A, h1sp) if a >= 0.2 or s) >= 2 or
            sum(1 for a in h2A if a <= 0.05) >= 2)
po2 = not any(out[g]["h1_any_fire"] for g in GRAPHS)
po2_kill = any(out[g]["h1_any_fire"] for g in GRAPHS)
po3_n = sum(1 for g in GRAPHS if out[g]["h2_cert"]["fires"])
po3 = po3_n >= 4
po3_kill = po3_n <= 2
po4 = all(out[g]["h"]["h1"]["max_jump"] <= 0.30 for g in GRAPHS)
# LOO for P-O1
loo_ok = True
for i in range(5):
    sub = [g for j, g in enumerate(GRAPHS) if j != i]
    ok = (sum(1 for g in sub if out[g]["h"]["h2"]["A_loop"] >= 0.2 and out[g]["h"]["h2"]["split"]) >= 3 and
          all(out[g]["h"]["h1"]["A_loop"] <= 0.05 for g in sub))
    loo_ok &= ok
out["verdicts"] = dict(h2A=h2A, h1A=h1A, PO1=bool(po1), PO1_killed=bool(po1_kill),
                       PO2=bool(po2), PO2_killed=bool(po2_kill), PO3_n=po3_n, PO3=bool(po3),
                       PO4=bool(po4), loo_ok=bool(loo_ok))
print(f"\nP-O1: {'ПОДТВЕРЖДЁН' if po1 else ('УБИТ' if po1_kill else 'не установлен')} "
      f"(A_h2={[round(a,2) for a in h2A]}, A_h1={[round(a,3) for a in h1A]}, LOO={loo_ok})")
print(f"P-O2 (слепота тройки при h=1): {'ПОДТВЕРЖДЁН' if po2 else 'УБИТ'}")
print(f"P-O3 (санити h=2): {po3_n}/5 -> {'ПОДТВЕРЖДЁН' if po3 else ('УБИТ' if po3_kill else 'не установлен')}")
print(f"P-O4 (гладкость h=1): {'подтверждён' if po4 else 'не подтверждён'}")
json.dump(out, open("/home/claude/ord001_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> ord001_results.json")
