"""GROK-006 calibration 2 on SPENT seed 413: update-direction cosines pre-burst; wd nodes 8e-4 / 1.5e-3 (period direction)."""
import time, sys
import numpy as np
exec(open("/home/claude/grok_cal.py").read().split("t0 = time.time()")[0])
t0 = time.time()

def run_switch_cos(seed, wd0, t_switch, wd1, steps, lr=10.0, D=512):
    global FRAC
    FRAC = 0.5
    (Xtr, Ytr), (Xte, Yte) = make_data(seed)
    rng = np.random.default_rng(seed + 7)
    W1 = rng.normal(0, 1 / np.sqrt(2 * P), (2 * P, D)); W2 = rng.normal(0, 1 / np.sqrt(D), (D, P))
    n = len(Xtr); rec = []; prev = None
    for t in range(steps):
        wd = wd0 if t < t_switch else wd1
        H = Xtr @ W1; A = H * H; Out = A @ W2
        G = (Out - Ytr) / n
        gW2 = A.T @ G; gA = G @ W2.T; gH = 2 * H * gA; gW1 = Xtr.T @ gH
        d1 = -lr * (gW1 + wd * W1); d2 = -lr * (gW2 + wd * W2)
        W1 += d1; W2 += d2
        if t >= t_switch:
            cur = np.concatenate([d1.ravel(), d2.ravel()])
            cos = float(cur @ prev / (np.linalg.norm(cur) * np.linalg.norm(prev) + 1e-30)) if prev is not None else 0.0
            prev = cur
            Hte = Xte @ W1; Ote = (Hte * Hte) @ W2
            acc = float((Ote.argmax(1) == Yte.argmax(1)).mean())
            ltr = float(((Out - Ytr) ** 2).sum(1).mean())
            wn = float(np.sqrt((W1 ** 2).sum() + (W2 ** 2).sum()))
            rec.append((t, acc, ltr, wn, cos))
        else:
            prev = None
    return np.array(rec)

wd1 = float(sys.argv[1])
r = run_switch_cos(413, 3e-4, 1000, wd1, 6000)
np.save(f"/home/claude/grok006_cal2_413_{wd1:g}.npy", r)
print(f"wd1={wd1:g}: recorded {len(r)} [{time.time()-t0:.0f}s]")
