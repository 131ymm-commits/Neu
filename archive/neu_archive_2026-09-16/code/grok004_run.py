"""GROK-004 — order of the alpha transition at fixed budget. Per PREREG (frozen 2026-09-02)."""
import json, os, time
import numpy as np
exec(open("/home/claude/grok_cal.py").read().split("t0 = time.time()")[0])
CK = "/home/claude/grok004_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()
def runf(seed, frac, steps):
    global FRAC
    FRAC = frac
    return run(seed, 10.0, 3e-4, 512, steps, rec_every=10)
for a in (0.20, 0.21, 0.22, 0.23, 0.24, 0.25):
    for sd in (501, 502):
        key = f"{a}_{sd}"
        if key in ck: continue
        h = runf(sd, a, 30000)
        v = h[:, 2]; O = float(np.median(v[-max(len(v) // 10, 5):]))
        cr = np.flatnonzero(v >= 0.5); tg = int(h[cr[0], 0]) if cr.size else None
        ck[key] = dict(alpha=a, seed=sd, O=O, t_grok=tg, train_ok=bool(h[:, 1].max() >= 0.99))
        json.dump(ck, open(CK, "w"), default=float)
        print(f"α={a} сид {sd}: O={O:.2f} t_grok={tg} train_ok={ck[key]['train_ok']} [{time.time()-t0:.0f}s]", flush=True)
A = (0.20, 0.21, 0.22, 0.23, 0.24, 0.25)
inter_both = sum(1 for a in A if all(0.2 < ck[f"{a}_{s}"]["O"] < 0.8 for s in (501, 502)))
inv = {}
for s in (501, 502):
    Os = [ck[f"{a}_{s}"]["O"] for a in A]
    inv[s] = sum(1 for i in range(len(Os) - 1) if Os[i + 1] < Os[i] - 0.05)
pc6a = inter_both <= 1; pc6a_kill = inter_both >= 3
pc6b = all(inv[s] <= 1 for s in inv); pc6b_kill = all(inv[s] >= 2 for s in inv)
# descriptive power-law fit of t_grok
pts = [(a, ck[f"{a}_{s}"]["t_grok"]) for a in A for s in (501, 502) if ck[f"{a}_{s}"]["t_grok"]]
fit = None
if len(pts) >= 4:
    best = None
    for ac in np.arange(0.150, 0.2101, 0.002):
        x = np.log([p[0] - ac for p in pts if p[0] > ac]); y = np.log([p[1] for p in pts if p[0] > ac])
        if len(x) < 4: continue
        nu, c = np.polyfit(x, y, 1); res = float(np.mean((y - (nu * x + c)) ** 2))
        if best is None or res < best[0]: best = (res, float(ac), float(-nu))
    fit = dict(alpha_c=best[1], nu=best[2], mse=best[0]) if best else None
ck["verdicts"] = dict(inter_both=inter_both, inversions=inv, PC6a=bool(pc6a), PC6a_killed=bool(pc6a_kill),
                      PC6b=bool(pc6b), PC6b_killed=bool(pc6b_kill), fit=fit)
json.dump(ck, open(CK, "w"), default=float)
print(f"\nO по α: " + " | ".join(f"{a}: {ck[f'{a}_501']['O']:.2f}/{ck[f'{a}_502']['O']:.2f}" for a in A))
print(f"P-C6a (резкость): промежуточных узлов у обоих сидов {inter_both} -> {'ПОДТВЕРЖДЁН' if pc6a else ('УБИТ' if pc6a_kill else 'не установлен')}")
print(f"P-C6b (монотонность): инверсий {inv} -> {'ПОДТВЕРЖДЁН' if pc6b else ('УБИТ' if pc6b_kill else 'не установлен')}")
print(f"описательно: степенной фит t_grok ∝ (α−α_c)^(−ν): {fit}")
print(f"[done {time.time()-t0:.0f}s]")
