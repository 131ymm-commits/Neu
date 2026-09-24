"""Dump the GROK-001 curves (same seeds/arms) for the TH-005 cell test. No labels are recomputed."""
import numpy as np, time
exec(open("/home/claude/grok_cal.py").read().split("t0 = time.time()")[0])
def runf(seed, frac, steps):
    global FRAC
    FRAC = frac
    return run(seed, 10.0, 3e-4, 512, steps, rec_every=2)
ARMS = [("main", 0.5, 3000, [201,202,203,204,205,206]),
        ("a30", 0.30, 10000, [211,212,213]),
        ("a25", 0.25, 16000, [221,222,223])]
out = {}; t0 = time.time()
for name, frac, steps, seeds in ARMS:
    for sd in seeds:
        h = runf(sd, frac, steps)
        out[f"{name}_{sd}"] = h
        np.savez("/home/claude/grok_curves.npz", **out)
        print(f"{name}_{sd}: {h.shape} [{time.time()-t0:.0f}s]", flush=True)
