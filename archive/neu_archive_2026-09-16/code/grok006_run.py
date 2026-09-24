"""GROK-006 — flicker as a periodic catapult cycle: clock, period-2 route, norm sawtooth, sharpness. Per PREREG (frozen 2026-09-02)."""
import json, os, sys, time
import numpy as np
exec(open("/home/claude/grok_cal.py").read().split("t0 = time.time()")[0])   # P, make_data
CK = "/home/claude/grok006_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()
LR, D = 10.0, 512

def make_grad(Xtr, Ytr):
    n = len(Xtr)
    def grad(W1, W2):
        H = Xtr @ W1; A = H * H; Out = A @ W2
        G = (Out - Ytr) / n
        gW2 = A.T @ G; gA = G @ W2.T; gH = 2 * H * gA; gW1 = Xtr.T @ gH
        return gW1, gW2, Out
    return grad

def sharpness(grad, W1, W2, v=None, iters=8, eps=1e-3):
    rng = np.random.default_rng(0)
    v1, v2 = (rng.normal(size=W1.shape), rng.normal(size=W2.shape)) if v is None else v
    lam = 0.0
    for _ in range(iters):
        nv = np.sqrt((v1 ** 2).sum() + (v2 ** 2).sum()); e = eps / nv
        g1p, g2p, _ = grad(W1 + e * v1, W2 + e * v2); g1m, g2m, _ = grad(W1 - e * v1, W2 - e * v2)
        h1, h2 = (g1p - g1m) / (2 * e), (g2p - g2m) / (2 * e)
        lam = float((h1 * v1).sum() + (h2 * v2).sum()) / nv ** 2
        nh = np.sqrt((h1 ** 2).sum() + (h2 ** 2).sum()); v1, v2 = h1 / nh, h2 / nh
    return lam, (v1, v2)

def run_flicker(seed, wd0, t_switch, wd1, post, with_sharp=True):
    global FRAC
    FRAC = 0.5
    (Xtr, Ytr), (Xte, Yte) = make_data(seed)
    grad = make_grad(Xtr, Ytr)
    rng = np.random.default_rng(seed + 7)
    W1 = rng.normal(0, 1 / np.sqrt(2 * P), (2 * P, D)); W2 = rng.normal(0, 1 / np.sqrt(D), (D, P))
    pre_acc = []; pre_sharp = []; rec = []; prev = None; v = None; ltr_prev = None; cold = []
    for t in range(t_switch + post):
        wd = wd0 if t < t_switch else wd1
        if with_sharp and t_switch - 10 <= t < t_switch:
            lam, v = sharpness(grad, W1, W2, v, iters=(30 if v is None else 8)); pre_sharp.append(lam * LR)
        g1, g2, Out = grad(W1, W2)
        ltr = float(((Out - Ytr) ** 2).sum(1).mean())
        sh = np.nan
        if with_sharp and t >= t_switch and (((t - t_switch) % 30 == 0) or (ltr_prev is not None and ltr > ltr_prev)):
            lam, v = sharpness(grad, W1, W2, v, iters=(30 if v is None else 8)); sh = lam * LR
            if (t - t_switch) % 300 == 0:
                lam_c, _ = sharpness(grad, W1, W2, None, iters=30); cold.append((t, sh, lam_c * LR))
        d1 = -LR * (g1 + wd * W1); d2 = -LR * (g2 + wd * W2)
        W1 += d1; W2 += d2
        if t >= t_switch:
            cur = np.concatenate([d1.ravel(), d2.ravel()])
            cos = float(cur @ prev / (np.linalg.norm(cur) * np.linalg.norm(prev) + 1e-30)) if prev is not None else np.nan
            prev = cur
            Hte = Xte @ W1; Ote = (Hte * Hte) @ W2
            acc = float((Ote.argmax(1) == Yte.argmax(1)).mean())
            wn = float(np.sqrt((W1 ** 2).sum() + (W2 ** 2).sum()))
            rec.append((t, acc, ltr, wn, cos, sh))
        elif t % 2 == 0:
            Hte = Xte @ W1; Ote = (Hte * Hte) @ W2
            pre_acc.append(float((Ote.argmax(1) == Yte.argmax(1)).mean()))
        ltr_prev = ltr if t >= t_switch else None
    return np.array(pre_acc), np.array(pre_sharp), np.array(rec), cold

def analyze(rec, pre_sharp):
    t, acc, ltr, wn, cos, sh = rec.T
    lam = (acc >= 0.5).astype(int); d = np.diff(np.concatenate([[0], lam, [0]])); ends = np.flatnonzero(d == -1)
    on = []
    for e in ends:
        if not on or e - on[-1] >= 10: on.append(int(e))
    on = np.array(on); out = dict(n_bursts=int(len(on)))
    if len(on) < 20:
        out["flicker"] = False; return out
    out["flicker"] = True
    ib = np.diff(on); out["cv"] = float(ib.std(ddof=1) / ib.mean()); out["T"] = float(ib.mean()); out["T_med"] = float(np.median(ib)); out["ib"] = ib.tolist()
    cp = [float(np.nanmean(cos[o - 5:o])) for o in on if o >= 6]; out["cos_pre_med"] = float(np.median(cp))
    out["cos_pre_frac_le"] = float(np.mean(np.array(cp) <= -0.5)); out["cos_pre_frac_ge"] = float(np.mean(np.array(cp) >= 0.5))
    ratios, decays, sratio, mids, premax = [], [], [], [], []
    for k in range(len(on) - 1):
        a, b = on[k], on[k + 1]
        if b - a < 20: continue
        trough = wn[a:a + 10].min(); peak = wn[a + 10:b].max(); ratios.append(peak / trough)
        decays.append(bool(wn[b - 1] < wn[a + 10]))
        w = sh[max(b - 6, 0):b]; w = w[~np.isnan(w)]
        m = a + (b - a) // 2; idx = np.arange(max(m - 15, 0), min(m + 16, len(sh))); ms = sh[idx]; ok = ~np.isnan(ms)
        if len(w) >= 2 and ok.any():
            j = idx[ok][np.argmin(np.abs(idx[ok] - m))]; mid = sh[j]; mids.append(float(mid)); premax.append(float(w.max()))
            sratio.append(float(w.max() / mid))
    out["saw_frac_ge12"] = float(np.mean(np.array(ratios) >= 1.2)); out["saw_med"] = float(np.median(ratios))
    out["decay_frac"] = float(np.mean(decays)); out["n_cycles"] = len(ratios)
    out["n_sharp_cycles"] = len(sratio)
    if sratio:
        out["sharp_ratio_med"] = float(np.median(sratio)); out["mid_sharp_med"] = float(np.median(mids)); out["pre_sharp_med"] = float(np.median(premax))
    out["pre_switch_sharp_med"] = float(np.median(pre_sharp)) if len(pre_sharp) else None
    return out

MAIN = [415, 416, 417, 418]; WDARM = [(419, 8e-4), (419, 1.5e-3), (419, 1e-3), (420, 8e-4), (420, 1.5e-3), (420, 1e-3)]
mode = sys.argv[1] if len(sys.argv) > 1 else "main"
if mode == "main":
    for sd in MAIN:
        key = f"main_{sd}"
        if key in ck: continue
        pre_acc, pre_sharp, rec, cold = run_flicker(sd, 3e-4, 1000, 1e-3, 6000, with_sharp=True)
        np.save(f"/home/claude/grok006_rec_{sd}.npy", rec)
        born = bool((pre_acc >= 0.5).any())
        a = analyze(rec, pre_sharp) if born else dict(flicker=False, n_bursts=0)
        a["born"] = born
        a["cold_check"] = [(int(x), float(y), float(z)) for x, y, z in cold]
        disc = [abs(y - z) / max(abs(z), 1e-9) for _, y, z in cold]
        a["cold_disc_med"] = float(np.median(disc)) if disc else None
        ck[key] = a; json.dump(ck, open(CK, "w"), default=float)
        print(f"сид {sd}: born={born} bursts={a.get('n_bursts')} CV={a.get('cv')} T={a.get('T')} cos_pre={a.get('cos_pre_med')} "
              f"saw≥1.2={a.get('saw_frac_ge12')} decay={a.get('decay_frac')} sharp_ratio={a.get('sharp_ratio_med')} "
              f"mid={a.get('mid_sharp_med')} pre_switch={a.get('pre_switch_sharp_med')} cold_disc={a.get('cold_disc_med')} [{time.time()-t0:.0f}s]", flush=True)
elif mode == "wd":
    for sd, wd1 in WDARM:
        key = f"wd_{sd}_{wd1:g}"
        if key in ck: continue
        pre_acc, pre_sharp, rec, cold = run_flicker(sd, 3e-4, 1000, wd1, 6000, with_sharp=False)
        born = bool((pre_acc >= 0.5).any())
        a = analyze(rec, pre_sharp) if born else dict(flicker=False, n_bursts=0)
        a["born"] = born; a["final_acc"] = float(rec[-1, 1]); a["frac_below"] = float(np.mean(rec[:, 1] < 0.5))
        ck[key] = a; json.dump(ck, open(CK, "w"), default=float)
        print(f"wd-арм сид {sd} wd1={wd1:g}: born={born} bursts={a.get('n_bursts')} T_med={a.get('T_med')} T_mean={a.get('T')} CV={a.get('cv')} final={a['final_acc']:.3f} [{time.time()-t0:.0f}s]", flush=True)
elif mode == "verdict":
    R = [ck.get(f"main_{s}") for s in MAIN]
    ok = [r for r in R if r and r.get("born") and r.get("flicker")]
    nread = len(ok)
    V = {}
    def allok(f): return nread >= 3 and all(f(r) for r in ok)
    def kill(f): return sum(1 for r in ok if f(r)) >= 3
    V["PC8a"] = dict(ok=allok(lambda r: r["cv"] <= 0.15), killed=kill(lambda r: r["cv"] >= 0.30))
    V["PC8b"] = dict(ok=allok(lambda r: r["cos_pre_med"] <= -0.5), killed=kill(lambda r: r["cos_pre_med"] >= 0.5))
    V["PC8c"] = dict(ok=allok(lambda r: r["saw_frac_ge12"] >= 0.8), killed=kill(lambda r: r["decay_frac"] >= 0.5))
    sh_ok = [r for r in ok if r.get("sharp_ratio_med") is not None and (r.get("cold_disc_med") is None or r["cold_disc_med"] <= 0.10)]
    def allsh(f): return len(sh_ok) >= 3 and all(f(r) for r in sh_ok)
    def killsh(f): return sum(1 for r in sh_ok if f(r)) >= 3
    V["PC8e"] = dict(ok=allsh(lambda r: r["sharp_ratio_med"] >= 1.15), killed=killsh(lambda r: r["sharp_ratio_med"] <= 1.0))
    V["PC8f"] = dict(ok=allsh(lambda r: r["mid_sharp_med"] >= 2.0 and r["pre_switch_sharp_med"] < 2.0), killed=killsh(lambda r: r["mid_sharp_med"] < 2.0))
    # P-C8d: period monotone in wd per seed (nodes with flicker only; need all three nodes)
    dres = {}
    for sd in (419, 420):
        Ts = {wd1: ck.get(f"wd_{sd}_{wd1:g}", {}).get("T_med") for wd1 in (8e-4, 1e-3, 1.5e-3)}
        dres[sd] = Ts
    def mono(Ts): return None not in Ts.values() and (Ts[8e-4] + 2 <= Ts[1e-3]) and (Ts[1e-3] <= Ts[1.5e-3] - 2)
    def anti(Ts): return None not in Ts.values() and (Ts[8e-4] - 2 >= Ts[1e-3]) and (Ts[1e-3] >= Ts[1.5e-3] + 2)
    V["PC8d"] = dict(ok=all(mono(dres[s]) for s in (419, 420)), killed=all(anti(dres[s]) for s in (419, 420)), T=dres)
    ck["verdicts"] = V; json.dump(ck, open(CK, "w"), default=float)
    for k, v in V.items():
        print(f"{k}: {'ПОДТВЕРЖДЁН' if v['ok'] else ('УБИТ' if v['killed'] else 'не установлен')} {v.get('T','')}")
print(f"[{time.time()-t0:.0f}s]")
