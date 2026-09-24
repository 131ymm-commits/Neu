"""GROK-006 calibration on SPENT seed 413 (GROK-002b): per-step val acc + val/train loss after wd switch.
Goal: arithmetic of achievability for laminar-phase law (counts, span, null non-degeneracy). NOT a test run."""
import json, time
import numpy as np
exec(open("/home/claude/grok_cal.py").read().split("t0 = time.time()")[0])
t0 = time.time()

def run_switch_dense2(seed, wd0, t_switch, wd1, steps, lr=10.0, D=512):
    global FRAC
    FRAC = 0.5
    (Xtr, Ytr), (Xte, Yte) = make_data(seed)
    rng = np.random.default_rng(seed + 7)
    W1 = rng.normal(0, 1 / np.sqrt(2 * P), (2 * P, D)); W2 = rng.normal(0, 1 / np.sqrt(D), (D, P))
    n = len(Xtr); rec = []
    for t in range(steps):
        wd = wd0 if t < t_switch else wd1
        H = Xtr @ W1; A = H * H; Out = A @ W2
        G = (Out - Ytr) / n
        gW2 = A.T @ G; gA = G @ W2.T; gH = 2 * H * gA; gW1 = Xtr.T @ gH
        W1 -= lr * (gW1 + wd * W1); W2 -= lr * (gW2 + wd * W2)
        if t >= t_switch:
            Hte = Xte @ W1; Ote = (Hte * Hte) @ W2
            acc = float((Ote.argmax(1) == Yte.argmax(1)).mean())
            lte = float(((Ote - Yte) ** 2).sum(1).mean()); ltr = float(((Out - Ytr) ** 2).sum(1).mean())
            wn = float(np.sqrt((W1 ** 2).sum() + (W2 ** 2).sum()))
            rec.append((t, acc, lte, ltr, wn))
    return np.array(rec)

r = run_switch_dense2(413, 3e-4, 1000, 1e-3, 6000)
np.save("/home/claude/grok006_cal_413.npy", r)
print(f"recorded {len(r)} steps [{time.time()-t0:.0f}s]")
