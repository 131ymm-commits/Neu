"""Stage A: pre-closure K in {0,1,2,3} -> freeze R*."""
import json, time, numpy as np
import sys; sys.path.insert(0, "/home/claude")
from lev002_common import *

t0 = time.time()
out = {}
for K in (0, 1, 2, 3):
    rec, capf = simulate(K, dag=False, ntraj=NTRAJ, T=T_TRAJ, seed_tag=K)
    out[K] = analyze_budgets(rec)
    out[K]["capfrac"] = capf
    print(f"K={K}: " + " ".join(f"{bn}:R={e['R'] and round(e['R'],2)} pl={int(e['plateau'])}"
          for bn, e in out[K].items() if bn.startswith('B')), f"cap={capf:.1e}", flush=True)

maxR = max(e["B3"]["R"] or 0 for e in out.values())
RSTAR = max(4.0, 2.5 * maxR)
print(f"\nmax R_B3 pre-closure = {maxR:.2f} -> R* = {RSTAR:.2f} (заморожено)")
json.dump(dict(preclosure={str(k): v for k, v in out.items()}, RSTAR=RSTAR),
          open("/home/claude/lev002_stageA.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s]")
