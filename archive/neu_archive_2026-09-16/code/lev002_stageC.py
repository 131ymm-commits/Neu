"""Stage C: reference runs — lifetimes and two-state confirmation."""
import json, time, numpy as np
import sys; sys.path.insert(0, "/home/claude")
from lev002_common import *

LO, HI = 3.0, 12.0
t0 = time.time()
out = {}
for K in range(3, 13):
    rec, _ = simulate(K, dag=False, ntraj=24, T=4000.0, seed_tag=5000 + K)
    tot = rec.astype(float)
    state = np.zeros(24, dtype=int)
    hot_time = np.zeros(24); dark_time = np.zeros(24)
    up_full = np.zeros(24); dn_full = np.zeros(24)
    for t in range(tot.shape[1]):
        x = tot[:, t]
        go_up = (state == 0) & (x > HI)
        go_dn = (state == 1) & (x < LO)
        up_full += go_up; dn_full += go_dn
        state = np.where(go_up, 1, np.where(go_dn, 0, state))
        hot_time += (state == 1) * DREC
        dark_time += (state == 0) * DREC
    ups, dns = up_full.sum(), dn_full.sum()
    T_hot = hot_time.sum() / max(dns, 1)
    T_dark = dark_time.sum() / max(ups, 1)
    frac_hot = hot_time.sum() / (hot_time.sum() + dark_time.sum())
    two_state = (ups >= 5) and (dns >= 5) and (0.02 < frac_hot < 0.98)
    out[K] = dict(ups=float(ups), dns=float(dns), T_hot=float(T_hot),
                  T_dark=float(T_dark), frac_hot=float(frac_hot), two_state=bool(two_state))
    print(f"K={K:2d}: ups={ups:5.0f} dns={dns:5.0f} T_hot={T_hot:8.1f} T_dark={T_dark:8.1f} "
          f"frac_hot={frac_hot:.3f} two_state={two_state}", flush=True)

json.dump(out, open("/home/claude/lev002_stageC.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s]")
