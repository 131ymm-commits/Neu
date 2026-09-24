"""DET-015 — root-consistent timescale estimator. Per PREREG (frozen 2026-08-23)."""
import json, time
import numpy as np

SEED = 20260839
LAGS = [1, 2, 3, 4, 6, 8]
T_STEPS, BURN_F = 3000, 150
MINVIS = 50

# ---------- simulators (frozen protocols) ----------
def sim_logistic(r, ntraj, seed, sigma=0.02, nb=40):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0.2, 0.8, ntraj)
    rec = np.empty((ntraj, T_STEPS), dtype=np.int64)
    for t in range(T_STEPS):
        x = np.clip(r * x * (1 - x) + sigma * rng.standard_normal(ntraj), 0.0, 1.0)
        rec[:, t] = np.minimum((x * nb).astype(np.int64), nb - 1)
    return rec[:, BURN_F:], nb

def sim_delayed(r, ntraj, seed, sigma=0.01, nbx=24):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0.2, 0.8, ntraj); y = rng.uniform(0.2, 0.8, ntraj)
    rec = np.empty((ntraj, T_STEPS), dtype=np.int64)
    for t in range(T_STEPS):
        xn = np.clip(r * x * (1 - y) + sigma * rng.standard_normal(ntraj), 0.0, 1.0)
        y = x; x = xn
        ix = np.minimum((x * nbx).astype(np.int64), nbx - 1)
        iy = np.minimum((y * nbx).astype(np.int64), nbx - 1)
        rec[:, t] = ix * nbx + iy
    return rec[:, BURN_F:], nbx * nbx

def sim_schlogl(fr, ntraj, seed):
    k1s, k4s = 5.75, 8.75
    SN1, Ww = 1.37154, 4.00578 - 1.37154
    k3 = SN1 + fr * Ww
    V, XMAX, LAM = 20, 4.6, 275.0
    N = int(np.ceil(V * XMAX)); nvec = np.arange(N + 1); xv = nvec / V
    Wp = k3 + k1s * xv**2; Wm = k4s * xv + xv**3
    Wp[-1] = 0.0; Wm[0] = 0.0
    pu, pd = Wp / LAM, Wm / LAM
    rng = np.random.default_rng(seed)
    rts = np.roots([-1.0, k1s, -k4s, k3]); rts = np.sort(rts[np.isreal(rts)].real)
    st = np.full(ntraj, int(round(V * rts[0])), dtype=np.int64)
    STEPS, STRIDE = 110000, 16
    rec = np.empty((ntraj, STEPS // STRIDE), dtype=np.int64)
    for i in range(STEPS):
        u = rng.random(ntraj)
        up = u < pu[st]; dn = (~up) & (u < pu[st] + pd[st])
        st += up.astype(np.int64) - dn.astype(np.int64)
        if (i + 1) % STRIDE == 0: rec[:, (i + 1) // STRIDE - 1] = st
    rec = rec[:, int(0.05 * rec.shape[1]):]
    return np.clip(rec // 2, 0, N // 2), N // 2 + 1

# ---------- eigen machinery ----------
def top_ev(data, nb, lag):
    a0 = data[:, :-lag].ravel(); a1 = data[:, lag:].ravel()
    C = np.bincount(a0 * nb + a1, minlength=nb * nb).reshape(nb, nb).astype(np.float64)
    keep = C.sum(1) >= MINVIS
    if keep.sum() < 4: return None
    T = C[np.ix_(keep, keep)]
    for _ in range(10):
        ok = T.sum(1) > 0
        if ok.all(): break
        T = T[np.ix_(ok, ok)]
    if T.shape[0] < 4: return None
    T = T / T.sum(1, keepdims=True)
    ev = np.linalg.eigvals(T)
    i_st = int(np.argmin(np.abs(ev - 1)))
    e = np.delete(ev, i_st)
    e = e[np.argsort(-np.abs(e))]
    am = np.abs(e)
    pair = len(e) > 1 and am[1] / am[0] > 0.95 and abs(np.angle(e[0]) + np.angle(e[1])) < 0.2
    return e[0], bool(pair)

def root_branch(lam, lag, z1):
    if lam is None: return None
    r_ = np.abs(lam) ** (1.0 / lag)
    th = np.angle(lam)
    cands = [r_ * np.exp(1j * (th + 2 * np.pi * k) / lag) for k in range(lag)]
    return cands[int(np.argmin([abs(c - z1) for c in cands]))]

def root_estimator(data, nb):
    e1 = top_ev(data, nb, 1)
    if e1 is None: return None
    z1 = e1[0]
    zs, pairs = [], []
    for lag in LAGS:
        e = top_ev(data, nb, lag)
        if e is None: continue
        z = root_branch(e[0], lag, z1)
        zs.append(z); pairs.append(e[1])
    if len(zs) < 5: return None
    zs = np.array(zs)
    zbar = zs.mean()
    rho = float(np.max(np.abs(zs - zbar)))
    ab = abs(zbar)
    t2 = float(-1.0 / np.log(ab)) if 0 < ab < 1 else np.nan
    return dict(zbar_re=float(zbar.real), zbar_im=float(zbar.imag), rho=rho,
                t2=t2, theta=float(np.angle(zbar)), n_lags=len(zs),
                pair1=bool(pairs[0]))

def jack_t2(data, nb, nblocks=40):
    n = data.shape[0]; bs = max(1, n // nblocks)
    ts = []
    for b in range(0, n, bs):
        sub = np.concatenate([data[:b], data[b + bs:]], axis=0)
        r_ = root_estimator(sub, nb)
        if r_ and r_["t2"] == r_["t2"]: ts.append(r_["t2"])
    return float(np.percentile(ts, 16)) if ts else np.nan

def shuffle_within(data, seed):
    rng = np.random.default_rng(seed)
    out = data.copy()
    for j in range(out.shape[0]): rng.shuffle(out[j])
    return out

t0 = time.time()
out = {"cal": {}, "flip": {}, "ns": {}, "fold": {}, "surr": {}}

# ===== Stage A: calibration -> freeze eps =====
sc, nbc = sim_schlogl(0.618, 80, SEED)
rc = root_estimator(sc, nbc)
out["cal"]["schlogl_0.618"] = rc
print(f"CAL Schlogl fr=0.618: rho={rc['rho']:.4f} t2={rc['t2']:.1f} th/pi={rc['theta']/np.pi:+.3f} [{time.time()-t0:.0f}s]", flush=True)
ld, nbl = sim_logistic(2.75, 320, SEED + 1)
rd = root_estimator(ld, nbl)
out["cal"]["logistic_2.75"] = rd
print(f"CAL logistic r=2.75: rho={rd['rho']:.4f} t2={rd['t2']:.1f} th/pi={rd['theta']/np.pi:+.3f} [{time.time()-t0:.0f}s]", flush=True)
EPS = 2.5 * max(rc["rho"], rd["rho"])
out["EPS"] = EPS
print(f"FROZEN: eps = {EPS:.4f}", flush=True)

# ===== flip targets =====
for i, r in enumerate([3.12, 3.16, 3.20]):
    rec, nb = sim_logistic(r, 320, SEED + 10 + i)
    e3 = root_estimator(rec, nb)
    e2 = root_estimator(rec[:80], nb)
    bud = abs(e2["t2"] - e3["t2"]) / e3["t2"] if (e2 and e3 and e3["t2"] == e3["t2"]) else np.inf
    j16 = jack_t2(rec, nb)
    ok = bool(e3 and e3["rho"] <= EPS and bud <= 0.20 and abs(abs(e3["theta"]) - np.pi) <= np.pi / 6)
    out["flip"][r] = dict(**e3, budget=float(bud), j16=j16, ok=ok)
    print(f"FLIP r={r}: rho={e3['rho']:.4f} t2={e3['t2']:.1f} (j16 {j16:.1f}) th/pi={e3['theta']/np.pi:+.3f} "
          f"bud={bud:.2f} ok={int(ok)} [{time.time()-t0:.0f}s]", flush=True)

# ===== NS targets =====
for i, r in enumerate([2.0745, 2.1036, 2.1327]):
    rec, nb = sim_delayed(r, 320, SEED + 20 + i)
    e3 = root_estimator(rec, nb)
    e2 = root_estimator(rec[:80], nb)
    bud = abs(e2["t2"] - e3["t2"]) / e3["t2"] if (e2 and e3 and e3["t2"] == e3["t2"]) else np.inf
    j16 = jack_t2(rec, nb)
    ok = bool(e3 and e3["rho"] <= EPS and abs(abs(e3["theta"]) - np.pi / 3) <= np.pi / 12)
    out["ns"][r] = dict(**e3, budget=float(bud), j16=j16, ok=ok)
    print(f"NS r={r}: rho={e3['rho']:.4f} t2={e3['t2']:.1f} (j16 {j16:.1f}) th/pi={e3['theta']/np.pi:+.3f} "
          f"bud={bud:.2f} ok={int(ok)} [{time.time()-t0:.0f}s]", flush=True)

# ===== fold: root vs plateau =====
for fr in (0.618, 0.734):
    rec, nb = (sc, nbc) if fr == 0.618 else sim_schlogl(fr, 80, SEED + 30)
    e = root_estimator(rec, nb)
    its = []
    for lag in (1, 2, 4):
        ev = top_ev(rec, nb, lag)
        if ev is not None:
            am = abs(ev[0])
            if 0 < am < 1: its.append(-lag / np.log(am))
    t_pl = float(np.mean(its)) if len(its) == 3 else np.nan
    pl_ok = len(its) == 3 and (max(its) - min(its)) / np.mean(its) < 0.2
    agree = abs(e["t2"] - t_pl) / t_pl if t_pl == t_pl else np.inf
    out["fold"][fr] = dict(**e, t2_plateau=t_pl, plateau_ok=bool(pl_ok), agree=float(agree))
    print(f"FOLD fr={fr}: t2_root={e['t2']:.1f} t2_plateau={t_pl:.1f} (pl_ok={int(pl_ok)}) "
          f"agree={agree:.2f} rho={e['rho']:.4f} [{time.time()-t0:.0f}s]", flush=True)

# ===== surrogates =====
for name, (rec, nb, tref) in {
    "flip_3.16": (sim_logistic(3.16, 320, SEED + 11)[0], 40, out["flip"][3.16]["t2"]),
    "ns_2.1036": (sim_delayed(2.1036, 320, SEED + 21)[0], 576, out["ns"][2.1036]["t2"]),
}.items():
    sh = shuffle_within(rec, SEED + 99)
    e = root_estimator(sh, nb)
    if e is None:
        rej, t2s = True, None
    else:
        rej = bool(e["rho"] > EPS or (e["t2"] == e["t2"] and e["t2"] <= 1.5) or e["t2"] != e["t2"])
        t2s = e["t2"]
    passes_bad = (e is not None and not rej and t2s == t2s and t2s >= 0.5 * tref)
    out["surr"][name] = dict(rejected=bool(rej), t2=t2s, rho=(e or {}).get("rho"), bad=bool(passes_bad))
    print(f"SURR {name}: rejected={rej} t2={t2s} rho={(e or {}).get('rho')} [{time.time()-t0:.0f}s]", flush=True)

# ===== degenerate (P-F5) =====
out["deg"] = {}
rec, nb = sim_delayed(1.55, 320, SEED + 41)
e = root_estimator(rec, nb)
out["deg"]["delayed_1.55"] = e
out["deg"]["logistic_2.75"] = rd
print(f"DEG delayed r=1.55: rho={e['rho']:.4f} t2={e['t2']:.1f}", flush=True)

# ===== verdicts =====
f_ok = sum(1 for v in out["flip"].values() if v["ok"])
f_bad = sum(1 for v in out["flip"].values() if v["rho"] > EPS or v["budget"] > 0.20)
pf1 = f_ok == 3
pf1_kill = f_bad >= 2
n_ok = sum(1 for v in out["ns"].values() if v["ok"])
n_bad = sum(1 for v in out["ns"].values() if v["rho"] > EPS)
pf2 = n_ok == 3
pf2_kill = n_bad >= 2
agrees = [out["fold"][fr]["agree"] for fr in (0.618, 0.734)]
pf3 = all(a <= 0.25 for a in agrees)
pf3_kill = all(a > 0.25 for a in agrees)
pf4 = all(v["rejected"] for v in out["surr"].values())
pf4_kill = any(v["bad"] for v in out["surr"].values())
pf5 = all(v and v["rho"] <= EPS and v["t2"] < 5 for v in out["deg"].values())
out["verdicts"] = dict(PF1=bool(pf1), PF1_killed=bool(pf1_kill), PF2=bool(pf2), PF2_killed=bool(pf2_kill),
                       PF3=bool(pf3), PF3_killed=bool(pf3_kill), PF4=bool(pf4), PF4_killed=bool(pf4_kill),
                       PF5=bool(pf5))
print(f"\nP-F1 (flip): {'ПОДТВЕРЖДЁН' if pf1 else ('УБИТ' if pf1_kill else 'не установлен')} ({f_ok}/3)")
print(f"P-F2 (NS): {'ПОДТВЕРЖДЁН' if pf2 else ('УБИТ' if pf2_kill else 'не установлен')} ({n_ok}/3)")
print(f"P-F3 (фолд): {'ПОДТВЕРЖДЁН' if pf3 else ('УБИТ' if pf3_kill else 'не установлен')} (agree {agrees[0]:.2f}/{agrees[1]:.2f})")
print(f"P-F4 (нуль): {'ПОДТВЕРЖДЁН' if pf4 else ('УБИТ' if pf4_kill else 'не установлен')}")
print(f"P-F5 (вырожденные): {'подтверждён' if pf5 else 'не подтверждён'}")

json.dump(out, open("/home/claude/det015_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det015_results.json")
