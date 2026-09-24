exec(open("/home/claude/grok_cal.py").read().split("t0 = time.time()")[0])
import time, numpy as np
def runf(seed, frac, steps, lr=10.0, wd=3e-4, D=512, rec_every=2):
    global FRAC
    FRAC = frac
    return run(seed, lr, wd, D, steps, rec_every=rec_every)
t0=time.time()
for frac, steps in ((0.2, 30000), (0.15, 30000)):
    h = runf(101, frac, steps)
    te50 = h[h[:,2]>=0.5]
    tg = int(te50[0,0]) if len(te50) else None
    print(f"α={frac}: t_grok={tg} val_final={h[-1,2]:.2f} [{time.time()-t0:.0f}s]", flush=True)
