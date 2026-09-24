"""DET-015c — root-consistent estimator v3: branch over BOTH pair members at root level.
Per PREREG. eps kept frozen from 015 stage A."""
import json, time
import numpy as np

exec(open("/home/claude/det015_run.py").read().split("t0 = time.time()")[0])

def root_branch_pair(lam, lag, z1):
    """All lag-th roots of both lam and conj(lam); pick closest to z1."""
    best, bd = None, np.inf
    for L in (lam, np.conj(lam)):
        r_ = np.abs(L) ** (1.0 / lag)
        th = np.angle(L)
        for k in range(lag):
            z = r_ * np.exp(1j * (th + 2 * np.pi * k) / lag)
            d = abs(z - z1)
            if d < bd: bd, best = d, z
    return best

def root_estimator(data, nb):
    e1 = top_ev(data, nb, 1)
    if e1 is None: return None
    z1 = e1[0] if e1[0].imag >= 0 else np.conj(e1[0])
    zs, pairs = [], []
    for lag in LAGS:
        e = top_ev(data, nb, lag)
        if e is None: continue
        zs.append(root_branch_pair(e[0], lag, z1)); pairs.append(e[1])
    if len(zs) < 5: return None
    zs = np.array(zs)
    zbar = zs.mean()
    rho = float(np.max(np.abs(zs - zbar)))
    ab = abs(zbar)
    t2 = float(-1.0 / np.log(ab)) if 0 < ab < 1 else np.nan
    return dict(zbar_re=float(zbar.real), zbar_im=float(zbar.imag), rho=rho,
                t2=t2, theta=float(np.angle(zbar)), n_lags=len(zs), pair1=bool(pairs[0]))

D15 = json.load(open("/home/claude/det015_results.json"))
EPS = D15["EPS"]
t0 = time.time()
out = {"EPS": EPS, "ns": {}, "flip": {}, "fold": {}, "surr": {}, "deg": {}}

for i, r in enumerate([2.0745, 2.1036, 2.1327]):
    rec, nb = sim_delayed(r, 320, SEED + 20 + i)
    e3 = root_estimator(rec, nb)
    e2 = root_estimator(rec[:80], nb)
    bud = abs(e2["t2"] - e3["t2"]) / e3["t2"] if (e2 and e3 and e3["t2"] == e3["t2"]) else np.inf
    ok = bool(e3 and e3["rho"] <= EPS and abs(abs(e3["theta"]) - np.pi / 3) <= np.pi / 12 and bud <= 0.20)
    out["ns"][r] = dict(**e3, budget=float(bud), ok=ok)
    print(f"NS r={r}: rho={e3['rho']:.4f} t2={e3['t2']:.1f} th/pi={e3['theta']/np.pi:+.3f} "
          f"bud={bud:.2f} ok={int(ok)} [{time.time()-t0:.0f}s]", flush=True)

for i, r in enumerate([3.12, 3.16, 3.20]):
    rec, nb = sim_logistic(r, 320, SEED + 10 + i)
    e3 = root_estimator(rec, nb)
    old = D15["flip"][str(r)]["t2"]
    out["flip"][r] = dict(t2=e3["t2"], t2_old=old, reldiff=float(abs(e3["t2"] - old) / old))
    print(f"FLIP r={r}: t2={e3['t2']:.1f} (diff {out['flip'][r]['reldiff']:.3f})", flush=True)

for fr in (0.618, 0.734):
    rec, nb = sim_schlogl(fr, 80, SEED if fr == 0.618 else SEED + 30)
    e = root_estimator(rec, nb)
    old = D15["fold"][str(fr)]["t2"]
    out["fold"][fr] = dict(t2=e["t2"], t2_old=old, reldiff=float(abs(e["t2"] - old) / old))
    print(f"FOLD fr={fr}: t2={e['t2']:.1f} (diff {out['fold'][fr]['reldiff']:.3f})", flush=True)

for name, (mk, nb, tref) in {
    "flip_3.16": (lambda: sim_logistic(3.16, 320, SEED + 11)[0], 40, out["flip"][3.16]["t2"]),
    "ns_2.1036": (lambda: sim_delayed(2.1036, 320, SEED + 21)[0], 576, out["ns"][2.1036]["t2"]),
}.items():
    sh = shuffle_within(mk(), SEED + 99)
    e = root_estimator(sh, nb)
    if e is None:
        rej, bad = True, False
    else:
        rej = bool(e["rho"] > EPS or (e["t2"] == e["t2"] and e["t2"] <= 1.5) or e["t2"] != e["t2"])
        bad = (not rej and e["t2"] == e["t2"] and e["t2"] >= 0.5 * tref)
    out["surr"][name] = dict(rejected=bool(rej), t2=(e or {}).get("t2"), rho=(e or {}).get("rho"), bad=bool(bad))
    print(f"SURR {name}: rejected={rej}", flush=True)

rec, nb = sim_delayed(1.55, 320, SEED + 41)
e = root_estimator(rec, nb)
out["deg"]["delayed_1.55"] = e
print(f"DEG delayed r=1.55: rho={e['rho']:.4f} t2={e['t2']:.1f}", flush=True)

n_ok = sum(1 for v in out["ns"].values() if v["ok"])
n_bad = sum(1 for v in out["ns"].values() if v["rho"] > EPS)
diffs = [v["reldiff"] for v in out["flip"].values()] + [v["reldiff"] for v in out["fold"].values()]
ph1 = n_ok == 3; ph1_kill = n_bad >= 2
ph2 = all(d <= 0.01 for d in diffs); ph2_kill = any(d > 0.05 for d in diffs)
ph3 = bool(e and e["rho"] <= EPS and e["t2"] < 5)
ph4 = all(v["rejected"] for v in out["surr"].values())
ph4_kill = any(v["bad"] for v in out["surr"].values())
out["verdicts"] = dict(PH1=bool(ph1), PH1_killed=bool(ph1_kill), PH2=bool(ph2), PH2_killed=bool(ph2_kill),
                       PH3=bool(ph3), PH4=bool(ph4), PH4_killed=bool(ph4_kill))
print(f"\nP-H1 (NS): {'ПОДТВЕРЖДЁН' if ph1 else ('УБИТ' if ph1_kill else 'не установлен')} ({n_ok}/3)")
print(f"P-H2: {'ПОДТВЕРЖДЁН' if ph2 else ('УБИТ' if ph2_kill else 'не установлен')} (max diff {max(diffs):.3f})")
print(f"P-H3: {'подтверждён' if ph3 else 'не подтверждён'}")
print(f"P-H4: {'ПОДТВЕРЖДЁН' if ph4 else ('УБИТ' if ph4_kill else 'не установлен')}")

json.dump(out, open("/home/claude/det015c_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det015c_results.json")
