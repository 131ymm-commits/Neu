"""GROK-006 calibration 3 (spent seed 413): sharpness (top Hessian eigenvalue of train MSE loss) via HVP power iteration
at chosen steps around known bursts. Checks achievability of the EoS prediction (lambda_max * lr vs 2)."""
import time
import numpy as np
exec(open("/home/claude/grok_cal.py").read().split("t0 = time.time()")[0])
t0 = time.time()
FRAC = 0.5
(Xtr, Ytr), (Xte, Yte) = make_data(413)
n = len(Xtr)

def grad(W1, W2):
    H = Xtr @ W1; A = H * H; Out = A @ W2
    G = (Out - Ytr) / n
    gW2 = A.T @ G; gA = G @ W2.T; gH = 2 * H * gA; gW1 = Xtr.T @ gH
    return gW1, gW2, float(((Out - Ytr) ** 2).sum(1).mean())

def hvp(W1, W2, v1, v2, eps=1e-3):
    nv = np.sqrt((v1 ** 2).sum() + (v2 ** 2).sum())
    e = eps / nv
    g1p, g2p, _ = grad(W1 + e * v1, W2 + e * v2)
    g1m, g2m, _ = grad(W1 - e * v1, W2 - e * v2)
    return (g1p - g1m) / (2 * e), (g2p - g2m) / (2 * e)

def sharpness(W1, W2, v=None, iters=20):
    rng = np.random.default_rng(0)
    if v is None:
        v1, v2 = rng.normal(size=W1.shape), rng.normal(size=W2.shape)
    else:
        v1, v2 = v
    lam = 0.0
    for _ in range(iters):
        h1, h2 = hvp(W1, W2, v1, v2)
        nv = np.sqrt((v1 ** 2).sum() + (v2 ** 2).sum())
        lam = float((h1 * v1).sum() + (h2 * v2).sum()) / nv ** 2
        nh = np.sqrt((h1 ** 2).sum() + (h2 ** 2).sum())
        v1, v2 = h1 / nh, h2 / nh
    return lam, (v1, v2)

# HVP consistency check
rng = np.random.default_rng(1)
W1 = rng.normal(0, 1 / np.sqrt(2 * P), (2 * P, 512)); W2 = rng.normal(0, 1 / np.sqrt(512), (512, P))
v1, v2 = rng.normal(size=W1.shape), rng.normal(size=W2.shape)
a = hvp(W1, W2, v1, v2, 1e-3); b = hvp(W1, W2, v1, v2, 1e-4)
print("HVP eps consistency rel diff:", float(np.sqrt(((a[0]-b[0])**2).sum()+((a[1]-b[1])**2).sum()) / np.sqrt((a[0]**2).sum()+(a[1]**2).sum())))

r = np.load("/home/claude/grok006_cal2_413_0.001.npy"); acc = r[:, 1]
lam_ = (acc >= 0.5).astype(int); d = np.diff(np.concatenate([[0], lam_, [0]])); ends = np.flatnonzero(d == -1)
on = []
for e in ends:
    if not on or e - on[-1] >= 10: on.append(int(e))
on = [o + 1000 for o in on]   # absolute step index (post starts at t=1000)
targets = {}
for o in on[3:6]:
    for k in range(-8, 3): targets[o + k] = "pre" if k < 0 else "burst"
    targets[o - 45] = "mid"
targets[998] = "before_switch"; targets[999] = "before_switch"
# training run replicating cal2 exactly
rng = np.random.default_rng(413 + 7)
W1 = rng.normal(0, 1 / np.sqrt(2 * P), (2 * P, 512)); W2 = rng.normal(0, 1 / np.sqrt(512), (512, P))
lr = 10.0; vprev = None; out = []
for t in range(max(targets) + 1):
    wd = 3e-4 if t < 1000 else 1e-3
    if t in targets:
        lam_w, vprev = sharpness(W1, W2, vprev, iters=8)
        lam, _ = sharpness(W1, W2, None, iters=30)
        g1, g2, L = grad(W1, W2)
        out.append((t, targets[t], lam, L))
        print(f"t={t} {targets[t]}: lambda*lr cold30={lam*lr:.3f} warm8={lam_w*lr:.3f} loss={L:.4f} [{time.time()-t0:.0f}s]", flush=True)
    g1, g2, _ = grad(W1, W2)
    W1 -= lr * (g1 + wd * W1); W2 -= lr * (g2 + wd * W2)
np.save("/home/claude/grok006_cal3b_413.npy", np.array([(a, {"pre":0,"burst":1,"mid":2,"before_switch":3}[b], c, dd) for a, b, c, dd in out]))
