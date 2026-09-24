"""GROK calibration 2 (spent seed 101): wd ladder + wd=0 control + battery features on pilot curves."""
import time
import numpy as np

exec(open("/home/claude/grok_cal.py").read().split("t0 = time.time()")[0])   # P, make_data, run
exec(open("/home/claude/ext001_run.py").read().split("t0 = time.time()")[0])  # feats, classify
TH = __import__("json").load(open("/home/claude/ext001_ckpt.json"))["th"]

def curve_feats(h):
    """Resample full recorded val-acc curve to 200 pts; i_on = first crossing of 0.5."""
    te = h[:, 2]
    x = np.interp(np.linspace(0, len(te) - 1, 200), np.arange(len(te)), te)
    cr = np.flatnonzero(x >= 0.5)
    if cr.size == 0 or cr[0] < 10:
        return None, None
    f = feats(x, int(cr[0]))
    return f, classify(f, TH)

t0 = time.time()
for wd, steps in ((1e-3, 3000), (3e-4, 3000), (1e-4, 8000), (0.0, 12000)):
    h = run(101, 10.0, wd, 512, steps, rec_every=2)
    te50 = h[h[:, 2] >= 0.5]
    tg = int(te50[0, 0]) if len(te50) else None
    f, lab = curve_feats(h)
    if f:
        print(f"wd={wd}: t_grok={tg} | S={f['S'] if f['S'] is None else round(f['S'],2)} rise={f['rise']:.1f} "
              f"z={f['z']:.2f} -> метка {lab} [{time.time()-t0:.0f}s]", flush=True)
    else:
        print(f"wd={wd}: t_grok={tg} (рождения нет в бюджете {steps}) val_final={h[-1,2]:.2f} [{time.time()-t0:.0f}s]", flush=True)
