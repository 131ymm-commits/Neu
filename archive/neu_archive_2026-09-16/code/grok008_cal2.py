"""GROK-008 calibration 2 (spent seed 101): transformer grokked with AdamW (lr 1e-3, wd 1), then wd raised; per-step test acc / loss recorded."""
import time, sys, math
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F
exec(open("/home/claude/grok008_cal.py").read().split("lr, wd, steps = ")[0])
wd1 = float(sys.argv[1]); t_switch = 6000; post = 6000
m = T1(); opt = torch.optim.AdamW(m.parameters(), lr=1e-3, weight_decay=1.0, betas=(0.9, 0.98)); t0 = time.time()
rec = []
for t in range(t_switch + post):
    if t == t_switch:
        for g in opt.param_groups: g["weight_decay"] = wd1
    opt.zero_grad(); out = m(Xtr); loss = F.cross_entropy(out, Ytr); loss.backward(); opt.step()
    if t >= t_switch or t % 50 == 0:
        with torch.no_grad():
            acc_te = (m(Xte).argmax(1) == Yte).float().mean().item(); acc_tr = (out.argmax(1) == Ytr).float().mean().item()
            wn = math.sqrt(sum((p ** 2).sum().item() for p in m.parameters()))
        rec.append((t, acc_tr, acc_te, loss.item(), wn))
        if t % 1000 == 0: print(f"t={t} tr={acc_tr:.3f} te={acc_te:.3f} loss={loss.item():.4f} wn={wn:.1f} [{time.time()-t0:.0f}s]", flush=True)
r = np.array(rec); np.save(f"/home/claude/grok008_cal2_wd{wd1:g}.npy", r)
post_r = r[r[:, 0] >= t_switch]; te = post_r[:, 2]
cross = int(np.sum(np.diff((te >= 0.5).astype(int)) != 0))
print(f"wd1={wd1:g}: post-switch te mean {te.mean():.3f} min {te.min():.3f} frac<0.5 {np.mean(te<0.5):.3f} crossings {cross} final {te[-1]:.3f} [{time.time()-t0:.0f}s]")
