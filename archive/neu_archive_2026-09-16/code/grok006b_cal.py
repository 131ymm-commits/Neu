"""GROK-006b calibration on SPENT seed 413: lr = 5 / 20 viability, burst counts, failure sharpness (lambda*lr), peak norm."""
import sys, json, time
import numpy as np
src = open("/home/claude/grok006_run.py").read().split("MAIN = [415")[0]
exec(src)
LR = float(sys.argv[1]); t0 = time.time()
pre_acc, pre_sharp, rec, cold = run_flicker(413, 3e-4, 1000, 1e-3, 6000, with_sharp=True)
np.save(f"/home/claude/grok006b_cal_413_lr{LR:g}.npy", rec)
born = bool((pre_acc >= 0.5).any()); tb = int(2 * np.flatnonzero(pre_acc >= 0.5)[0]) if born else None
a = analyze(rec, pre_sharp) if born else dict(flicker=False, n_bursts=0)
a["born"] = born; a["t_birth"] = tb; a["final_acc"] = float(rec[-1, 1]); a["cold"] = cold
a.pop("ib", None)
json.dump(a, open(f"/home/claude/grok006b_cal_413_lr{LR:g}.json", "w"), default=float)
print(f"lr={LR:g}: born={born} t_birth={tb} bursts={a.get('n_bursts')} T_med={a.get('T_med')} CV={a.get('cv')} cos={a.get('cos_pre_med')} "
      f"saw={a.get('saw_frac_ge12')} pre_sharp={a.get('pre_sharp_med')} mid={a.get('mid_sharp_med')} pre_switch={a.get('pre_switch_sharp_med')} final={a['final_acc']:.3f} [{time.time()-t0:.0f}s]", flush=True)
