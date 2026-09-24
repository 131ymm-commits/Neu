"""GROK pre-freeze calibration (spent seeds 101/102) — Gromov-style one-hidden-layer x^2 MLP,
modular addition, full-batch GD + weight decay, pure numpy. Goal: find (lr, wd, D, steps)
giving a clean grokking curve; record shapes for prereg arithmetic. NOT a test run."""
import time
import numpy as np

P = 53
FRAC = 0.5

def make_data(seed):
    rng = np.random.default_rng(seed)
    pairs = np.array([(a, b) for a in range(P) for b in range(P)])
    rng.shuffle(pairs)
    ntr = int(FRAC * len(pairs))
    tr, te = pairs[:ntr], pairs[ntr:]
    def enc(ps):
        X = np.zeros((len(ps), 2 * P))
        X[np.arange(len(ps)), ps[:, 0]] = 1
        X[np.arange(len(ps)), P + ps[:, 1]] = 1
        Y = np.zeros((len(ps), P))
        Y[np.arange(len(ps)), (ps[:, 0] + ps[:, 1]) % P] = 1
        return X, Y
    return enc(tr), enc(te)

def run(seed, lr, wd, D, steps, rec_every=5):
    (Xtr, Ytr), (Xte, Yte) = make_data(seed)
    rng = np.random.default_rng(seed + 7)
    W1 = rng.normal(0, 1 / np.sqrt(2 * P), (2 * P, D))
    W2 = rng.normal(0, 1 / np.sqrt(D), (D, P))
    n = len(Xtr)
    hist = []
    for t in range(steps):
        H = Xtr @ W1
        A = H * H
        Out = A @ W2
        G = (Out - Ytr) / n
        gW2 = A.T @ G
        gA = G @ W2.T
        gH = 2 * H * gA
        gW1 = Xtr.T @ gH
        W1 -= lr * (gW1 + wd * W1)
        W2 -= lr * (gW2 + wd * W2)
        if t % rec_every == 0:
            Hte = Xte @ W1; Ote = (Hte * Hte) @ W2
            acc_tr = float((Out.argmax(1) == Ytr.argmax(1)).mean())
            acc_te = float((Ote.argmax(1) == Yte.argmax(1)).mean())
            hist.append((t, acc_tr, acc_te))
    return np.array(hist)

t0 = time.time()
for lr, wd, D, steps in ((2.0, 2e-3, 512, 4000), (5.0, 1e-3, 512, 4000), (2.0, 5e-3, 512, 4000)):
    h = run(101, lr, wd, D, steps)
    tr_at = h[np.searchsorted(h[:, 1], 0.99), 0] if h[:, 1].max() > 0.99 else None
    te_cross = h[h[:, 2] >= 0.5]
    te_at = te_cross[0, 0] if len(te_cross) else None
    print(f"lr={lr} wd={wd}: train99@{tr_at} valcross50@{te_at} val_final={h[-1,2]:.2f} "
          f"[{time.time()-t0:.0f}s]", flush=True)
