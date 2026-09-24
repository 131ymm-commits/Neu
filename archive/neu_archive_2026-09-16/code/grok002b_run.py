"""GROK-002b — flicker of the level and its route (flip certificate). Per PREREG (frozen 2026-09-02)."""
import json, os, time
import numpy as np
exec(open("/home/claude/grok_cal.py").read().split("t0 = time.time()")[0])
CK = "/home/claude/grok002b_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()

def run_switch_dense(seed, wd0, t_switch, wd1, steps, lr=10.0, D=512):
    global FRAC
    FRAC = 0.5
    (Xtr, Ytr), (Xte, Yte) = make_data(seed)
    rng = np.random.default_rng(seed + 7)
    W1 = rng.normal(0, 1 / np.sqrt(2 * P), (2 * P, D)); W2 = rng.normal(0, 1 / np.sqrt(D), (D, P))
    n = len(Xtr); pre, post = [], []
    for t in range(steps):
        wd = wd0 if t < t_switch else wd1
        H = Xtr @ W1; A = H * H; Out = A @ W2
        G = (Out - Ytr) / n
        gW2 = A.T @ G; gA = G @ W2.T; gH = 2 * H * gA; gW1 = Xtr.T @ gH
        W1 -= lr * (gW1 + wd * W1); W2 -= lr * (gW2 + wd * W2)
        if (t < t_switch and t % 2 == 0) or t >= t_switch:
            Hte = Xte @ W1; Ote = (Hte * Hte) @ W2
            acc = float((Ote.argmax(1) == Yte.argmax(1)).mean())
            (pre if t < t_switch else post).append((t, acc))
    return np.array(pre), np.array(post)

def altfrac(x):
    s = np.sign(np.diff(np.asarray(x, float))); s = s[s != 0]
    return (float(np.mean(s[1:] != s[:-1])), int(len(s) - 1)) if len(s) >= 8 else (None, int(len(s)))

for sd in (413, 414):
    key = str(sd)
    if key in ck: continue
    pre, post = run_switch_dense(sd, 3e-4, 1000, 1e-3, 6000)
    born = bool((pre[:, 1] >= 0.5).any())
    v = post[:, 1]
    cross = int(np.sum(np.diff((v >= 0.5).astype(int)) != 0))
    A, nA = altfrac(v)
    # dominant period via autocorrelation of the post segment (descriptive)
    vv = v - v.mean(); ac = np.correlate(vv, vv, mode="full")[len(vv) - 1:]; ac = ac / (ac[0] + 1e-12)
    lags = np.arange(1, min(400, len(ac) - 1)); dom = int(lags[np.argmax(ac[1:400])]) if len(ac) > 400 else None
    cross_pre = int(np.sum(np.diff((pre[:, 1] >= 0.5).astype(int)) != 0))
    ck[key] = dict(born=born, cross=cross, A=A, nA=nA, dom_lag=dom, frac_below=float(np.mean(v < 0.5)),
                   cross_pre=cross_pre, val_post_every50=[float(q) for q in v[::50]])
    json.dump(ck, open(CK, "w"), default=float)
    print(f"сид {sd}: родилась={born}, пересечений после переключения {cross} (до: {cross_pre}), доля ниже 0.5 = {np.mean(v<0.5):.2f}, "
          f"A = {None if A is None else round(A,3)} (n={nA}), доминирующий лаг АКФ = {dom} шагов [{time.time()-t0:.0f}s]", flush=True)

r = [ck[str(s)] for s in (413, 414)]
pc5a = all(x["cross"] >= 20 for x in r); pc5a_kill = all(x["cross"] < 10 for x in r)
pc5b = all(x["A"] is not None and x["A"] >= 0.75 for x in r)
pc5b_kill = all(x["A"] is not None and x["A"] <= 0.55 for x in r)
ck["verdicts"] = dict(PC5a=bool(pc5a), PC5a_killed=bool(pc5a_kill), PC5b=bool(pc5b), PC5b_killed=bool(pc5b_kill))
json.dump(ck, open(CK, "w"), default=float)
print(f"P-C5a (мерцание воспроизводится): {'ПОДТВЕРЖДЁН' if pc5a else ('УБИТ' if pc5a_kill else 'не установлен')}")
print(f"P-C5b (маршрут — flip): {'ПОДТВЕРЖДЁН' if pc5b else ('УБИТ — нерегулярно' if pc5b_kill else 'не установлен')}")
print(f"[done {time.time()-t0:.0f}s]")
