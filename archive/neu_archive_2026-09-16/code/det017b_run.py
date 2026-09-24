"""DET-017b — additive kink statistic. Per PREREG (frozen 2026-08-26).
Reuses DET-017 machinery verbatim; test curves from ckpt; subcritical curves regenerated (same seeds)."""
import json, time
import numpy as np

exec(open("/home/claude/det017_run.py").read().split('ck = json.load')[0])

CK17 = json.load(open("/home/claude/det017_ckpt.json"))
t0 = time.time()

# Stage A additive floor: regenerate subcritical curves with the same seeds
subs = []
ls_sub = np.linspace(0.2, 0.6, NK)
for r in range(3):
    Md, _ = curves(ls_sub, SEED + 1000 * r, twin=False)
    Mt, _ = curves(ls_sub, SEED + 1000 * r + 500, twin=True)
    kd, _, _ = kink_fit(ls_sub, Md)
    kt, _, _ = kink_fit(ls_sub, Mt)
    subs.append(kd - kt)
    print(f"SUB r{r}: K_add={subs[-1]:.4f} (v4 Rc был {CK17['floor']['sub_Rc'][r]:.1f}) [{time.time()-t0:.0f}s]", flush=True)
floor_add = 2.5 * max(subs)
print(f"FROZEN: floor_add = {floor_add:.4f}")

# Test reps from stored curves
kadds, rcs, fires = [], [], 0
for r in range(5):
    e = CK17[f"rep{r}"]
    ls = np.array(e["ls"]); Md = np.array(e["M"]); Mt = np.array(e["Mt"])
    kd, kbp, bi = kink_fit(ls, Md)
    kt, _, _ = kink_fit(ls, Mt)
    ka = kd - kt
    kadds.append(ka); rcs.append(e["Rc"])
    fire = bool(ka >= floor_add and (not e["split"]) and e["interior"] and e["cons"])
    fires += fire
    print(f"rep{r}: K_add={ka:.3f} (Rc был {e['Rc']:.0f}) fires={int(fire)}")

cv = lambda a: float(np.std(a) / np.mean(a))
cv_add, cv_rc = cv(kadds), cv(rcs)
spread_add = max(subs) / max(min(subs), 1e-12)
pa1 = fires == 5
pa1_kill = fires <= 3
pa2 = cv_add <= 0.5 * cv_rc
pa2_kill = cv_add >= cv_rc
pa3 = spread_add < 12.4
out = dict(sub_Kadd=subs, floor_add=floor_add, test_Kadd=kadds, fires=fires,
           cv_add=cv_add, cv_rc=cv_rc, spread_add=spread_add,
           verdicts=dict(PA1=bool(pa1), PA1_killed=bool(pa1_kill),
                         PA2=bool(pa2), PA2_killed=bool(pa2_kill), PA3=bool(pa3)))
json.dump(out, open("/home/claude/det017b_results.json", "w"), default=float)
print(f"\nP-A1: {fires}/5 -> {'ПОДТВЕРЖДЁН' if pa1 else ('УБИТ' if pa1_kill else 'не установлен')}")
print(f"P-A2: CV_add={cv_add:.3f} против CV_Rc={cv_rc:.3f} -> "
      f"{'ПОДТВЕРЖДЁН' if pa2 else ('УБИТ' if pa2_kill else 'не установлен')}")
print(f"P-A3: субкритический разброс {spread_add:.1f} против 12.4 -> {pa3}")
print(f"[{time.time()-t0:.0f}s]")
