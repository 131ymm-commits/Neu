"""DET-014 — transient certificate on Gardner-Collins toggle CME; open-loop twin.
Per PREREG (frozen 2026-08-23)."""
import json, time
import numpy as np

SEED = 20260838
OMEGA = 25
DT = 0.01
STRIDE = 10          # dt_s = 0.1
T_BUDGET = 400.0
NSAMP_C1 = int(T_BUDGET / (DT * STRIDE))    # 4000
T_PERS = 100.0
NSAMP_C2 = int(T_PERS / (DT * STRIDE))      # 1000
NTRAJ = 80
A_DEG = [1.2, 1.4, 1.6]
A_WIN = list(np.round(np.linspace(1.8, 2.6, 12), 4))

def mf_states(a):
    def f(s):
        u, v = s
        return np.array([a / (1 + v * v) - u, a / (1 + u * u) - v])
    def run(s):
        s = np.array(s, float); h = 0.01
        for _ in range(20000):
            s = s + h * f(s)
        return s
    s1 = run([3.0, 0.1]); s2 = run([0.1, 3.0])
    return s1, s2, bool(abs(s1[0] - s2[0]) > 0.5)

def sim_toggle(a, ntraj, seed, nsamp, n0u, n0v, twin=False):
    rng = np.random.default_rng(seed)
    nu = np.full(ntraj, n0u, dtype=np.int64) if np.isscalar(n0u) else np.array(n0u, dtype=np.int64)
    nv = np.full(ntraj, n0v, dtype=np.int64) if np.isscalar(n0v) else np.array(n0v, dtype=np.int64)
    ru = np.empty((ntraj, nsamp)); rv = np.empty((ntraj, nsamp))
    for i in range(nsamp * STRIDE):
        cu = nu / OMEGA; cv = nv / OMEGA
        bu = OMEGA * a / (1 + cv * cv)
        bv = np.full(ntraj, OMEGA * a) if twin else OMEGA * a / (1 + cu * cu)
        nu = np.maximum(nu + rng.poisson(bu * DT) - rng.poisson(nu * DT), 0)
        nv = np.maximum(nv + rng.poisson(bv * DT) - rng.poisson(nv * DT), 0)
        if (i + 1) % STRIDE == 0:
            k = (i + 1) // STRIDE - 1
            ru[:, k] = nu / OMEGA; rv[:, k] = nv / OMEGA
    return ru, rv

def _runs_const(sym):
    idx = np.flatnonzero(sym)
    if idx.size == 0: return np.empty(0, dtype=int)
    if idx.size == 1: return np.array([1])
    brk = ~((np.diff(idx) == 1) & (sym[idx[1:]] == sym[idx[:-1]]))
    bounds = np.r_[0, np.flatnonzero(brk) + 1, idx.size]
    return np.diff(bounds)

def rot_L(ru, rv, ufp, vfp, dec=1):
    u = ru[:, ::dec] - ufp; v = rv[:, ::dec] - vfp
    phi = np.arctan2(v, u)
    dphi = np.angle(np.exp(1j * np.diff(phi, axis=1)))
    g = np.sign(dphi).astype(np.int8)
    allr = np.concatenate([_runs_const(row) for row in g])
    return float(np.median(allr)), int(allr.size)

def c1_stats(ru, u_dark_exit, u_hot_entry):
    tw, tc = [], []
    for row in ru:
        hot = np.flatnonzero(row >= u_hot_entry)
        if hot.size == 0: continue
        h0 = hot[0]
        dark = np.flatnonzero(row[:h0] <= u_dark_exit)
        d0 = dark[-1] if dark.size else 0
        tw.append(h0 * DT * STRIDE)
        tc.append((h0 - d0) * DT * STRIDE)
    return np.array(tw), np.array(tc)

def jack_S(tw, tc, nb=10):
    n = len(tw); bs = max(1, n // nb)
    Ss = []
    for b0 in range(0, n, bs):
        m = np.ones(n, bool); m[b0:b0 + bs] = False
        if m.sum() < 3: continue
        med_c = np.median(tc[m])
        if med_c > 0: Ss.append(np.median(tw[m]) / med_c)
    return float(np.percentile(Ss, 16)) if Ss else np.nan

def sym_fp(a):
    r = np.roots([1.0, 0.0, 1.0, -a])
    r = r[np.isreal(r)].real
    return float(r[r > 0][0])

t0 = time.time()
out = {"deg": {}, "win": {}}

# Stage A: degenerate (rotation floor); monostable by construction
for i, a in enumerate(A_DEG):
    s = sym_fp(a)
    n0 = int(round(s * OMEGA))
    ru, rv = sim_toggle(a, NTRAJ, SEED + i, 1000, n0, n0)
    L10, n10 = rot_L(ru, rv, s, s, dec=1)
    L100, n100 = rot_L(ru, rv, s, s, dec=10)
    out["deg"][a] = dict(L10=L10, n10=n10, L100=L100, n100=n100)
    print(f"DEG a={a}: L_rot(s10)={L10:.1f} (n={n10}) L_rot(s100)={L100:.1f} [{time.time()-t0:.0f}s]", flush=True)

LSTAR = max(8.0, 2.5 * max(max(v["L10"], v["L100"]) for v in out["deg"].values()))
out["LSTAR_ROT"] = LSTAR
print(f"FROZEN: L*_rot = {LSTAR:.1f}", flush=True)

for i, a in enumerate(A_WIN):
    s1, s2, bist = mf_states(a)
    e = dict(bistable=bist)
    if not bist:
        e.update(struct_silent=True, det=False)
        out["win"][a] = e
        print(f"WIN a={a}: МОНОСТАБИЛЬНО (структурное молчание) [{time.time()-t0:.0f}s]", flush=True)
        continue
    hi_s, lo_s = (s1, s2) if s1[0] > s2[0] else (s2, s1)
    u_hi, u_lo = hi_s[0], lo_s[0]
    d = u_hi - u_lo
    u_mid, u_de, u_he = u_lo + 0.5 * d, u_lo + 0.2 * d, u_lo + 0.8 * d
    # C1: dark start
    ru, rv = sim_toggle(a, NTRAJ, SEED + 1000 + i, NSAMP_C1,
                        int(round(u_lo * OMEGA)), int(round(lo_s[1] * OMEGA)))
    tw, tc = c1_stats(ru, u_de, u_he)
    npass = len(tw)
    S = float(np.median(tw) / np.median(tc)) if npass else np.nan
    Sj = jack_S(tw, tc) if npass >= 20 else np.nan
    c1 = bool(npass >= 20 and Sj == Sj and Sj >= 3.0)
    # C2': hot start, data vs open-loop twin
    ruh, _ = sim_toggle(a, NTRAJ, SEED + 3000 + i, NSAMP_C2,
                        int(round(u_hi * OMEGA)), int(round(hi_s[1] * OMEGA)))
    p_hot = float((ruh[:, -1] > u_mid).mean())
    rut, _ = sim_toggle(a, NTRAJ, SEED + 4000 + i, NSAMP_C2,
                        int(round(u_hi * OMEGA)), int(round(hi_s[1] * OMEGA)), twin=True)
    p_twin = float((rut[:, -1] > u_mid).mean())
    c2 = bool(p_hot >= 0.15 and p_hot - p_twin >= 0.10)
    # rotation cross-leg on C1 recordings around symmetric point
    s = sym_fp(a)
    L10, n10 = rot_L(ru, rv, s, s, dec=1)
    L100, n100 = rot_L(ru, rv, s, s, dec=10)
    e.update(u_lo=u_lo, u_hi=u_hi, npass=npass, S=S, S_j16=Sj, C1=c1,
             p_hot=p_hot, p_twin=p_twin, C2=c2, det=bool(c1 and c2),
             L10=L10, n10=n10, L100=L100, n100=n100)
    out["win"][a] = e
    print(f"WIN a={a}: пасс={npass} S={S:.1f} Sj16={Sj if Sj==Sj else -1:.1f} C1={int(c1)} | "
          f"p_hot={p_hot:.2f} p_twin={p_twin:.2f} C2={int(c2)} | det={int(c1 and c2)} | "
          f"L_rot {L10:.0f}/{L100:.0f} [{time.time()-t0:.0f}s]", flush=True)

wins = [out["win"][a].get("det", False) for a in A_WIN]
astar = None
for j in range(len(A_WIN) - 1):
    if wins[j] and wins[j + 1]:
        astar = A_WIN[j]; break
out["astar"] = astar
band = [a for a in A_WIN if out["win"][a].get("det", False)]
budget_cut = [a for a in A_WIN if out["win"][a].get("bistable") and out["win"][a].get("npass", 99) < 20]
rot_fire = []
for j in range(len(A_WIN) - 1):
    for key in ("L10", "L100"):
        if (out["win"][A_WIN[j]].get(key, 0) >= LSTAR and out["win"][A_WIN[j + 1]].get(key, 0) >= LSTAR):
            rot_fire.append((A_WIN[j], key))

pe1 = (astar is not None and 2.0182 <= astar <= 2.3091 and
       not any(out["win"][a].get("det", False) for a in A_WIN if a <= 1.9455))
pe1_kill = (astar is None or (astar is not None and astar <= 1.9455))
det_nodes = [a for a in band]
pe2 = (len(det_nodes) > 0 and all(out["win"][a]["p_twin"] <= 0.05 for a in det_nodes))
pe2_kill = any(out["win"][a]["p_twin"] >= out["win"][a]["p_hot"] - 0.10 for a in det_nodes) if det_nodes else False
pe3 = (len(rot_fire) == 0)
pe4 = len(budget_cut) > 0
pe5 = (astar is not None and astar <= 2.1636)
out["verdicts"] = dict(PE1=bool(pe1), PE1_killed=bool(pe1_kill), PE2=bool(pe2),
                       PE2_killed=bool(pe2_kill), PE3=bool(pe3), PE4=bool(pe4), PE5=bool(pe5),
                       band=band, budget_cut=budget_cut)
print(f"\na* = {astar} (a_c = 2.0); полоса детекции: {band}; бюджетный обрыв: {budget_cut}")
print(f"P-E1: {'ПОДТВЕРЖДЁН' if pe1 else ('УБИТ' if pe1_kill else 'не установлен')}")
print(f"P-E2 (двойник): {'ПОДТВЕРЖДЁН' if pe2 else ('УБИТ' if pe2_kill else 'не установлен')}")
print(f"P-E3 (вращение молчит): {'ПОДТВЕРЖДЁН' if pe3 else 'УБИТ'} {rot_fire if rot_fire else ''}")
print(f"P-E4 (граница бюджета): {'наблюдается' if pe4 else 'не наблюдается'}")
print(f"P-E5 (тайминг): {'подтверждён' if pe5 else 'нет'}")

json.dump(out, open("/home/claude/det014_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det014_results.json")
