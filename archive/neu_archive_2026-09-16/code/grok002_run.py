"""GROK-002 — hysteresis of the generalization level in weight decay. Per PREREG (frozen 2026-09-02).
Usage: python3 grok002_run.py birth | death   (two parallel processes, separate checkpoints)"""
import sys, json, os, time
import numpy as np
exec(open("/home/claude/grok_cal.py").read().split("t0 = time.time()")[0])
ARM = sys.argv[1]
CK = f"/home/claude/grok002_{ARM}_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()

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

if ARM == "birth":
    for wd in (5e-4, 7e-4, 1e-3, 1.5e-3):
        for sd in (401, 402):
            key = f"{wd}_{sd}"
            if key in ck: continue
            FRAC = 0.5
            h = run_switch(sd, wd, 10**9, wd, 10000)
            born = bool((h[:, 2] >= 0.5).any())
            t_b = int(h[np.flatnonzero(h[:, 2] >= 0.5)[0], 0]) if born else None
            ck[key] = dict(wd=wd, seed=sd, born=born, t_birth=t_b, train_final=float(h[-1, 1]), val_final=float(h[-1, 2]),
                           train_ok=bool(h[:, 1].max() >= 0.99))
            json.dump(ck, open(CK, "w"), default=float)
            print(f"рождение wd={wd} сид {sd}: {'рождён@'+str(t_b) if born else 'НЕТ'} (train max {h[:,1].max():.2f}) [{time.time()-t0:.0f}s]", flush=True)
else:
    for wd in (1e-3, 2e-3, 2.5e-3, 3e-3, 4e-3):
        for sd in (411, 412):
            key = f"{wd}_{sd}"
            if key in ck: continue
            FRAC = 0.5
            h = run_switch(sd, 3e-4, 1000, wd, 9000)
            post = h[h[:, 0] >= 1000]
            v = post[:, 2]
            perm_dead = bool(np.median(v[-max(len(v) // 10, 5):]) < 0.5)
            dip = bool(v.min() < 0.5 and v[-1] >= 0.9)
            t_d = int(post[np.flatnonzero(v < 0.5)[0], 0]) if (v < 0.5).any() else None
            ck[key] = dict(wd=wd, seed=sd, perm_dead=perm_dead, dip=dip, t_below=t_d, min_val=float(v.min()),
                           val_final=float(v[-1]), train_final=float(post[-1, 1]),
                           val_post=[float(q) for q in v])          # curve kept for the reversed reading
            json.dump(ck, open(CK, "w"), default=float)
            print(f"смерть wd→{wd} сид {sd}: {'НЕОБРАТИМО' if perm_dead else ('провал+возрождение' if dip else 'выжил')} "
                  f"(min {v.min():.2f}, финал {v[-1]:.2f}) [{time.time()-t0:.0f}s]", flush=True)
print(f"[{ARM} done {time.time()-t0:.0f}s]")
