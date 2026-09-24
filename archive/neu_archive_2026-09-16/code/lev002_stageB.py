"""Stage B: window K=4..12, real + DAG, all budgets; surrogates; budget curve."""
import json, time, numpy as np
import sys; sys.path.insert(0, "/home/claude")
from lev002_common import *

t0 = time.time()
out = {"real": {}, "dag": {}, "surr": [], "conv": None}
for K in range(4, 13):
    for kind, dag in (("real", False), ("dag", True)):
        rec, capf = simulate(K, dag=dag, ntraj=NTRAJ, T=T_TRAJ, seed_tag=1000 * (2 if dag else 1) + K)
        e = analyze_budgets(rec)
        e["capfrac"] = capf
        out[kind][K] = e
        print(f"{kind} K={K}: " + " ".join(f"{bn}:R={x['R'] and round(x['R'],2)} pl={int(x['plateau'])}"
              for bn, x in e.items() if bn.startswith('B')), f"cap={capf:.1e}", flush=True)
        if kind == "real" and K == 8:
            pts = []
            for nt in (20, 40, 80, 160, 320):
                res, _ = spectral(rec[:nt])
                t2m, t3m = res[LAG_MAIN]
                pts.append(dict(n=nt, R=None if not (t2m == t2m and t3m == t3m) else float(t2m / t3m)))
            out["conv"] = dict(K=8, pts=pts)
            print("   conv@K=8:", [(p['n'], p['R'] and round(p['R'], 2)) for p in pts], flush=True)
        if kind == "real" and K in (4, 8, 12):
            sub = rec[:BUDGETS["B2"]].copy()
            rs = np.random.default_rng(777)
            for j in range(sub.shape[0]):
                rs.shuffle(sub[j])
            res, _ = spectral(sub)
            t2m, t3m = res[LAG_MAIN]
            Rm = t2m / t3m if (t2m == t2m and t3m == t3m) else np.nan
            out["surr"].append(dict(K=K, R=None if Rm != Rm else float(Rm),
                                    t2=None if t2m != t2m else float(t2m)))
            print(f"   surr K={K}: R={None if Rm!=Rm else round(Rm,2)}", flush=True)

json.dump(out, open("/home/claude/lev002_stageB.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s]")
