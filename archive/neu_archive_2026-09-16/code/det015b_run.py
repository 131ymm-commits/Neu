"""DET-015b — root-consistent estimator v2: conjugate canonicalization (Im >= 0).
Per PREREG. Single frozen change vs det015_run.py; eps kept from 015 stage A."""
import json, time
import numpy as np

exec(open("/home/claude/det015_run.py").read().split("t0 = time.time()")[0])

# --- v2: canonicalized root estimator (overrides) ---
def canon(lam):
    return np.conj(lam) if lam.imag < 0 else lam

def root_estimator(data, nb):
    e1 = top_ev(data, nb, 1)
    if e1 is None: return None
    z1 = canon(e1[0])
    zs, pairs = [], []
    for lag in LAGS:
        e = top_ev(data, nb, lag)
        if e is None: continue
        z = root_branch(canon(e[0]), lag, z1)
        zs.append(z); pairs.append(e[1])
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
    ok = bool(e3 and e3["rho"] <= EPS and abs(abs(e3["theta"]) - np.pi / 3) <= np.pi / 12)
    out["ns"][r] = dict(**e3, budget=float(bud), ok=ok)
    print(f"NS r={r}: rho={e3['rho']:.4f} t2={e3['t2']:.1f} th/pi={e3['theta']/np.pi:+.3f} "
          f"bud={bud:.2f} ok={int(ok)} [{time.time()-t0:.0f}s]", flush=True)

for i, r in enumerate([3.12, 3.16, 3.20]):
    rec, nb = sim_logistic(r, 320, SEED + 10 + i)
    e3 = root_estimator(rec, nb)
    old = D15["flip"][str(r)]["t2"]
    d = abs(e3["t2"] - old) / old
    out["flip"][r] = dict(t2=e3["t2"], t2_old=old, reldiff=float(d))
    print(f"FLIP r={r}: t2={e3['t2']:.1f} (015: {old:.1f}, diff {d:.3f}) [{time.time()-t0:.0f}s]", flush=True)

for fr in (0.618, 0.734):
    rec, nb = sim_schlogl(fr, 80, SEED if fr == 0.618 else SEED + 30)
    e = root_estimator(rec, nb)
    old = D15["fold"][str(fr)]["t2"]
    d = abs(e["t2"] - old) / old
    out["fold"][fr] = dict(t2=e["t2"], t2_old=old, reldiff=float(d))
    print(f"FOLD fr={fr}: t2={e['t2']:.1f} (015: {old:.1f}, diff {d:.3f}) [{time.time()-t0:.0f}s]", flush=True)

for name, (mk, nb, tref_key) in {
    "flip_3.16": (lambda: sim_logistic(3.16, 320, SEED + 11)[0], 40, ("flip", 3.16)),
    "ns_2.1036": (lambda: sim_delayed(2.1036, 320, SEED + 21)[0], 576, ("ns", 2.1036)),
}.items():
    sh = shuffle_within(mk(), SEED + 99)
    e = root_estimator(sh, nb)
    tref = out[tref_key[0]][tref_key[1]].get("t2") or D15["flip"][str(tref_key[1])]["t2"]
    if e is None:
        rej, bad = True, False
    else:
        rej = bool(e["rho"] > EPS or (e["t2"] == e["t2"] and e["t2"] <= 1.5) or e["t2"] != e["t2"])
        bad = (not rej and e["t2"] == e["t2"] and e["t2"] >= 0.5 * tref)
    out["surr"][name] = dict(rejected=bool(rej), t2=(e or {}).get("t2"), rho=(e or {}).get("rho"), bad=bool(bad))
    print(f"SURR {name}: rejected={rej} [{time.time()-t0:.0f}s]", flush=True)

rec, nb = sim_delayed(1.55, 320, SEED + 41)
e = root_estimator(rec, nb)
out["deg"]["delayed_1.55"] = e
print(f"DEG delayed r=1.55: rho={e['rho']:.4f} t2={e['t2']:.1f} [{time.time()-t0:.0f}s]", flush=True)

n_ok = sum(1 for v in out["ns"].values() if v["ok"])
n_bad = sum(1 for v in out["ns"].values() if v["rho"] > EPS)
pg1 = n_ok == 3
pg1_kill = n_bad >= 2
diffs = [v["reldiff"] for v in out["flip"].values()] + [v["reldiff"] for v in out["fold"].values()]
pg2 = all(d <= 0.01 for d in diffs)
pg2_kill = any(d > 0.05 for d in diffs)
pg3 = bool(e and e["rho"] <= EPS and e["t2"] < 5)
pg4 = all(v["rejected"] for v in out["surr"].values())
pg4_kill = any(v["bad"] for v in out["surr"].values())
out["verdicts"] = dict(PG1=bool(pg1), PG1_killed=bool(pg1_kill), PG2=bool(pg2), PG2_killed=bool(pg2_kill),
                       PG3=bool(pg3), PG4=bool(pg4), PG4_killed=bool(pg4_kill))
print(f"\nP-G1 (NS): {'ПОДТВЕРЖДЁН' if pg1 else ('УБИТ' if pg1_kill else 'не установлен')} ({n_ok}/3)")
print(f"P-G2 (тождественность вещественных): {'ПОДТВЕРЖДЁН' if pg2 else ('УБИТ' if pg2_kill else 'не установлен')} (max diff {max(diffs):.3f})")
print(f"P-G3 (вырожденная NS): {'подтверждён' if pg3 else 'не подтверждён'}")
print(f"P-G4 (нуль): {'ПОДТВЕРЖДЁН' if pg4 else ('УБИТ' if pg4_kill else 'не установлен')}")

json.dump(out, open("/home/claude/det015b_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det015b_results.json")
