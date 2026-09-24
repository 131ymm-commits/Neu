import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ck3 = json.load(open("/home/claude/pre003_ckpt.json"))
ckb = json.load(open("/home/claude/pre003b_ckpt.json"))
Vb = ckb["verdicts"]

fig, ax = plt.subplots(1, 3, figsize=(13, 3.9))

a = ax[0]
al = [0, 0.5, 1]
D12 = [ck3["verdicts"]["D"][k] for k in ("0", "0.5", "1")]
D24 = [Vb["D"][k] for k in ("0", "0.5", "1")]
a.plot(al, D12, "s--", color="#bbb", label="n = 12+12 (PRE-003: не разрешено)")
a.plot(al, D24, "o-", color="#1f5fbf", lw=2, ms=9, label="n = 24+24 (PRE-003b)")
a.axhline(0.5, color="k", lw=0.8)
a.set_xticks(al); a.set_xticklabels(["0\n(равномерный)", "0.5\n(сублинейный)", "1\n(линейный PA)"])
a.set_ylabel("D(α) = медиана MW по парам")
a.set_ylim(0.4, 0.8)
a.set_title("Кривая предсказуемости: граница внезапности\nмежду α = 0.5 и α = 1 (Δ(0.5→1) = +0.17)")
a.legend(fontsize=8)

b = ax[1]
x = np.arange(3)
w = 0.25
cols = {"0": "#1f5fbf", "0.5": "#2a9d3a", "1": "#e07b00"}
for i, alk in enumerate(("0", "0.5", "1")):
    mws = [Vb["res"][f"{alk}|{K}"]["mw"] for K in (6, 8, 10)]
    ps = [Vb["res"][f"{alk}|{K}"]["p"] for K in (6, 8, 10)]
    bars = b.bar(x + (i - 1) * w, mws, w, color=cols[alk], label=f"α = {alk}")
    for xx, m, p in zip(x + (i - 1) * w, mws, ps):
        b.annotate("*" if p <= 0.05 else "", (xx, m + 0.005), ha="center", fontsize=11)
b.axhline(0.5, color="k", lw=0.8)
b.set_xticks(x); b.set_xticklabels(["пара 6\n(ранняя)", "пара 8\n(средняя)", "пара 10\n(поздняя)"])
b.set_ylim(0.4, 0.8)
b.set_ylabel("MW (n = 24+24)")
b.set_title("По парам: линейный умирает с ростом графа\n(0.65 → 0.52 → 0.48); * = p ≤ 0.05")
b.legend(fontsize=8)

c = ax[2]
med = [9, 8, 7]
warn = D24
c.plot(med, warn, "o-", color="#7b2d8b", lw=2, ms=10)
for m, wv, alk in zip(med, warn, ("0", "0.5", "1")):
    c.annotate(f"α={alk}", (m, wv), fontsize=9, xytext=(6, 6), textcoords="offset points")
c.set_xlabel("медиана Kc (когда рождается)")
c.set_ylabel("D(α) (насколько предвещено)")
c.axhline(0.5, color="k", lw=0.8)
c.set_title("Обмен «скорость ↔ предсказуемость»:\nраньше рождается — внезапнее наступает")
c.invert_xaxis()

fig.suptitle("PRE-003/003b — форма границы внезапности: сублинейная канализация предупреждение сохраняет, "
             "линейная убивает; ускорение рождения покупается непредсказуемостью", fontsize=10)
fig.tight_layout(rect=[0, 0, 1, 0.9])
fig.savefig("/home/claude/pre003_fig.png", dpi=140)
print("ok")
