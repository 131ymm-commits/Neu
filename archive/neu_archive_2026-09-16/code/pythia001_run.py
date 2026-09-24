"""PYTHIA-001 — frozen certificates on Pythia v1 zero-shot trajectories. Per PREREG (2026-09-02)."""
import json, sys
import numpy as np
sys.path.insert(0, "/home/claude"); from pythia001_lib import *
from scipy.stats import spearmanr
out = dict(std={}, ded={}, ctrl={}, lambada={})
for fam, models in (("std", STD), ("ded", DED)):
    for m in models:
        steps, series, mmlu = load_model(m)
        out[fam][m] = {}
        for t in TASKS:
            out[fam][m][t] = certificate(steps, series(t, "acc"), CHANCE[t])
        c = certificate(steps, mmlu, 0.25); out["ctrl"][m] = c
        ppl = series("lambada_openai", "ppl"); yl = -np.log10(ppl)
        out["lambada"][m] = dict(acc=out[fam][m]["lambada_openai"], ppl=certificate(steps, yl, float(yl[0])))
json.dump(out, open("/home/claude/pythia001_results.json", "w"), default=float, ensure_ascii=False, indent=1)

# ---------- verdicts (standard family) ----------
labs = [(m, t, out["std"][m][t]["label"]) for m in STD for t in TASKS]
born = [(m, t, l) for m, t, l in labs if l != "нет рождения"]
n_step = sum(1 for _, _, l in born if l == "ступень"); n_ramp = sum(1 for _, _, l in born if l == "плавный"); n_und = len(born) - n_step - n_ramp
share = n_step / len(born) if born else None
print(f"кривых {len(labs)}, с рождением {len(born)}: ступень {n_step}, плавный {n_ramp}, неразличимо {n_und} -> доля ступеней {share:.2f}")
PP1 = dict(ok=bool(share is not None and share <= 0.20), killed=bool(share is not None and share >= 0.50), share=share, n=len(born))
rhos = {}
for t in TASKS:
    pts = [(np.log10(SIZE[m]), out["std"][m][t]["birth"]) for m in STD if out["std"][m][t]["birth"] is not None]
    if len(pts) >= 5:
        xs, ys = zip(*pts); r = spearmanr(xs, ys).correlation
        loo = [spearmanr([x for j, x in enumerate(xs) if j != i], [y for j, y in enumerate(ys) if j != i]).correlation for i in range(len(xs))]
        rhos[t] = dict(rho=float(r), n=len(pts), loo=[float(v) for v in loo])
print("P-P2 ρ по задачам:", {t: (round(v["rho"], 2), v["n"]) for t, v in rhos.items()})
if rhos:
    frac_ok = np.mean([v["rho"] <= -0.8 for v in rhos.values()]); frac_weak = np.mean([abs(v["rho"]) < 0.5 for v in rhos.values()])
    PP2 = dict(ok=bool(frac_ok >= 0.70), killed=bool(frac_weak >= 0.50), frac_ok=float(frac_ok), frac_weak=float(frac_weak), rhos=rhos)
else:
    PP2 = dict(ok=False, killed=False, note="не читается: нет задач с ≥ 5 рождениями")
la = [(m, out["lambada"][m]["acc"]["label"], out["lambada"][m]["ppl"]["label"]) for m in STD]
decided = [(m, a, p) for m, a, p in la if a in ("ступень", "плавный") or p in ("ступень", "плавный")]
if len(decided) >= 5:
    agree = np.mean([a == p for _, a, p in decided]); PP3 = dict(ok=bool(agree >= 0.80), killed=bool(agree <= 0.50), agree=float(agree), n=len(decided), pairs=la)
else:
    PP3 = dict(ok=False, killed=False, note="не читается", pairs=la)
print("P-P3 lambada пары (acc, ppl):", [(m.replace('pythia-', ''), a, p) for m, a, p in la])
ctrl_ok = sum(1 for m in STD if out["ctrl"][m]["label"] == "нет рождения")
print(f"контроль MMLU: «нет рождения» у {ctrl_ok}/8 (выигрыши: {[round(out['ctrl'][m]['gain'], 3) for m in STD]})")
# deduped agreement (descriptive)
agree_ded = [out["std"][s][t]["label"] == out["ded"][d][t]["label"] for s, d in zip(["pythia-70m", "pythia-160m", "pythia-410m", "pythia-1.4b", "pythia-2.8b", "pythia-6.9b", "pythia-12b"], ["pythia-70m-deduped", "pythia-160m-deduped", "pythia-410m-deduped", "pythia-1.4b-deduped", "pythia-2.8b-deduped", "pythia-6.9b-deduped", "pythia-12b-deduped"]) for t in TASKS]
print(f"согласие меток std/deduped (описательно): {np.mean(agree_ded):.2f} ({sum(agree_ded)}/{len(agree_ded)})")
V = dict(PP1=PP1, PP2=PP2, PP3=PP3, ctrl_ok=ctrl_ok, ded_agree=float(np.mean(agree_ded)))
out["verdicts"] = V
json.dump(out, open("/home/claude/pythia001_results.json", "w"), default=float, ensure_ascii=False, indent=1)
for k in ("PP1", "PP2", "PP3"):
    v = V[k]; print(k, "ПОДТВЕРЖДЁН" if v.get("ok") else ("УБИТ" if v.get("killed") else "не установлен"))
# table of labels
print("\nметки (std):")
print("size      " + " ".join(f"{t[:9]:>10}" for t in TASKS))
for m in STD:
    print(f"{m.replace('pythia-',''):9} " + " ".join(f"{out['std'][m][t]['label'][:10]:>10}" for t in TASKS))
print("\nшаг рождения log10 (std):")
for m in STD:
    print(f"{m.replace('pythia-',''):9} " + " ".join(f"{(out['std'][m][t]['birth'] if out['std'][m][t]['birth'] is not None else float('nan')):10.2f}" for t in TASKS))
