import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])
M = 10
ck = json.load(open("/home/claude/pre002_ckpt.json"))
V = ck["verdicts"]["res"]
UNIF_MW_DYN = {"6": 0.63, "8": 0.61, "10": 0.77}

fig, ax = plt.subplots(1, 3, figsize=(13, 3.9))

a = ax[0]
for i, K in enumerate(["6", "8", "10"]):
    u, p = UNIF_MW_DYN[K], V[K]["mw_dyn"]
    a.plot([i - 0.15, i + 0.15], [u, p], "-", color="#999", lw=1)
    a.plot([i - 0.15], [u], "o", color="#1f5fbf", ms=9)
    a.plot([i + 0.15], [p], "o", color="#e07b00", ms=9)
    a.annotate(f"Δ={p-u:+.2f}", (i, (u + p) / 2), fontsize=8, ha="center",
               xytext=(18, 0), textcoords="offset points")
a.axhline(0.5, color="k", lw=0.8)
a.set_xticks(range(3))
a.set_xticklabels([f"квантильная пара {q}\n(униф K*={q} ↔ PA K*={ck['verdicts']['matched'][q]})"
                   for q in ["6", "8", "10"]], fontsize=7)
a.set_ylim(0.38, 0.85)
a.set_ylabel("MW различения «неминуемо/далеко»")
a.plot([], [], "o", color="#1f5fbf", label="равномерный рост")
a.plot([], [], "o", color="#e07b00", label="преференциальный (PA)")
a.set_title("P-K1 ветвь (b): предупреждение схлопывается\n(медиана Δ = −0.17; все p_PA > 0.25)")
a.legend(fontsize=8, loc="upper left")

b = ax[1]
kcu = [k_cycle(edges_seq(M, sg), M) for sg in range(5301, 5501)]
kcp = [ck["stageA"]["pa_kc"][s] for s in list(ck["stageA"]["pa_kc"])[:200]]
bins = np.arange(1.5, 25.5)
b.hist(kcu, bins=bins, alpha=0.55, color="#1f5fbf", label=f"униф (медиана {ck['stageA']['med_unif']:.0f})", density=True)
b.hist(kcp, bins=bins, alpha=0.55, color="#e07b00", label=f"PA (медиана {ck['stageA']['med_pa']:.0f})", density=True)
b.set_xlabel("Kc (ребро первого цикла)"); b.set_ylabel("плотность")
b.set_title("P-K3: PA рождает раньше (направление ✓),\nно кромка MW 0.70 не взята (0.69) — убит по букве")
b.legend(fontsize=8)

c = ax[2]
x = np.arange(3)
sp = [V[K]["sp"] for K in ["6", "8", "10"]]
mh = [V[K]["mw_haz"] for K in ["6", "8", "10"]]
md = [V[K]["mw_dyn"] for K in ["6", "8", "10"]]
c.bar(x - 0.22, sp, 0.22, color="#2a9d3a", label="Спирмен(AUC_p, ρ_reach)")
c.bar(x, md, 0.22, color="#e07b00", label="MW динамики")
c.bar(x + 0.22, mh, 0.22, color="#b48a00", label="MW hazard'а")
c.axhline(0.5, color="k", lw=0.8)
c.set_xticks(x); c.set_xticklabels([f"пара {q}" for q in ["6", "8", "10"]])
c.set_ylim(0, 1.0)
c.set_title("Считывание живо (0.85–0.89),\nчитать нечего: снимок не знает будущего")
c.legend(fontsize=7, loc="upper right")

fig.suptitle("PRE-002 — правило роста и предсказуемость рождения: канализованный (PA) рост — раньше и внезапнее; "
             "равномерный — позже, но с частичным предупреждением", fontsize=10)
fig.tight_layout(rect=[0, 0, 1, 0.9])
fig.savefig("/home/claude/pre002_fig.png", dpi=140)
print("ok")
