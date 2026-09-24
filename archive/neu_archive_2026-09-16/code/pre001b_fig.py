import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ck = json.load(open("/home/claude/pre001b_ckpt.json"))
V = ck["verdicts"]["res"]
KS = [6, 8, 10]

fig, ax = plt.subplots(1, 3, figsize=(13, 3.9))

a = ax[0]
x = np.arange(3)
mw = [V[str(k)]["mw"] for k in KS]
mwr = [V[str(k)]["mw_rho"] for k in KS]
mwt = [V[str(k)]["mw_twin"] for k in KS]
a.bar(x - 0.25, mw, 0.25, color="#1f5fbf", label="динамика (AUC_p)")
a.bar(x, mwr, 0.25, color="#e07b00", label="структурный hazard ρ_reach")
a.bar(x + 0.25, mwt, 0.25, color="#88b5e8", label="двойник (метки оригинала)")
a.axhline(0.5, color="k", lw=0.8)
a.axhline(0.7, color="#c33", lw=1, ls=":", label="порог P-J1 = 0.70")
for i, k in enumerate(KS):
    a.annotate(f"p={V[str(k)]['p_perm']:.2f}", (i - 0.25, mw[i] + 0.01), fontsize=7, ha="center", color="#1f5fbf")
a.set_xticks(x); a.set_xticklabels([f"K* = {k}" for k in KS])
a.set_ylim(0.4, 0.85)
a.set_ylabel("MW AUC (неминуемо против далеко)")
a.set_title("Различение классов: динамика ≈ hazard\n(узкое место — сам снимок)")
a.legend(fontsize=7, loc="upper left")

b = ax[1]
g = ck["10"]["graphs"]
for lab, col, mk in (("imm", "#c33", "o"), ("dist", "#1f5fbf", "s")):
    xs = [x_["rho"] for x_ in g if x_["label"] == lab]
    ys = [x_["auc"] for x_ in g if x_["label"] == lab]
    b.scatter(xs, ys, s=45, color=col, marker=mk, alpha=0.75,
              label="Kc−K ≤ 2 (неминуемо)" if lab == "imm" else "Kc−K ≥ 5 (далеко)")
b.set_xlabel("ρ_reach (доля замыкающих пар)")
b.set_ylabel("AUC_p (динамика)")
b.set_title(f"K* = 10: динамика читает достижимость\nСпирмен = {V['10']['sp_rho']:+.2f}")
b.legend(fontsize=7)

c = ax[2]
sps = [V[str(k)]["sp_rho"] for k in KS]
c.plot(KS, sps, "o-", color="#2a9d3a", label="Спирмен(AUC_p, ρ_reach)")
c.plot(KS, mw, "s--", color="#1f5fbf", label="MW различения классов")
c.axhline(0.5, color="k", lw=0.8, alpha=0.5)
c.set_xlabel("K*"); c.set_ylim(0.3, 1.0)
c.set_title("Считывание почти без потерь (≈0.93)\nпри слабой предсказуемости будущего")
c.legend(fontsize=7, loc="center left")

fig.suptitle("PRE-001b — читает ли динамика близость закрытия при фиксированном K: частично (K*=10: MW 0.77, p=0.007); "
             "динамика ≈ безызбыточный считыватель снимка, но снимок слабо знает будущее", fontsize=9.5)
fig.tight_layout(rect=[0, 0, 1, 0.9])
fig.savefig("/home/claude/pre001b_fig.png", dpi=140)
print("ok")
