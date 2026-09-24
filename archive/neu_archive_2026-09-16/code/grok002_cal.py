"""GROK-002 pre-freeze calibration (spent seed 101): does a grokked network DIE when wd is raised, and how?"""
import numpy as np, time
exec(open("/home/claude/grok_cal.py").read().split("t0 = time.time()")[0])

def run_switch(seed, wd0, t_switch, wd1, steps, lr=10.0, D=512, rec_every=2):
    (Xtr, Ytr), (Xte, Yte) = make_data(seed)
    rng = np.random.default_rng(seed + 7)
    W1 = rng.normal(0, 1 / np.sqrt(2 * P), (2 * P, D)); W2 = rng.normal(0, 1 / np.sqrt(D), (D, P))
    n = len(Xtr); hist = []
    for t in range(steps):
        wd = wd0 if t < t_switch else wd1
        H = Xtr @ W1; A = H * H; Out = A @ W2
        G = (Out - Ytr) / n
        gW2 = A.T @ G; gA = G @ W2.T; gH = 2 * H * gA; gW1 = Xtr.T @ gH
        W1 -= lr * (gW1 + wd * W1); W2 -= lr * (gW2 + wd * W2)
        if t % rec_every == 0:
            Hte = Xte @ W1; Ote = (Hte * Hte) @ W2
            hist.append((t, float((Out.argmax(1) == Ytr.argmax(1)).mean()), float((Ote.argmax(1) == Yte.argmax(1)).mean())))
    return np.array(hist)

t0 = time.time()
for wd1 in (1e-3, 2e-3, 3e-3):
    h = run_switch(101, 3e-4, 1000, wd1, 9000)
    te = h[:, 2]; post = h[h[:, 0] >= 1000]
    below = post[post[:, 2] < 0.5]
    t_death = int(below[0, 0]) if len(below) else None
    print(f"wd→{wd1}: val@1000={te[np.searchsorted(h[:,0],1000)]:.2f} смерть@{t_death} val_final={te[-1]:.2f} "
          f"train_final={h[-1,1]:.2f} [{time.time()-t0:.0f}s]", flush=True)
    if t_death is not None:
        seg = post[:, 2]
        i1 = int(np.flatnonzero(seg < 0.8)[0]) if (seg < 0.8).any() else None
        i2 = int(np.flatnonzero(seg < 0.2)[0]) if (seg < 0.2).any() else None
        print(f"   переезд 0.8→0.2: {None if i1 is None or i2 is None else (i2 - i1) * 2} шагов; ожидание до 0.8: {None if i1 is None else i1 * 2} шагов")
