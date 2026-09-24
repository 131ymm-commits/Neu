import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

C = json.load(open("/home/claude/ord001_curves.json"))
D1 = json.load(open("/home/claude/ord001_results.json"))
Db = json.load(open("/home/claude/ord001b_ckpt.json"))
GR = ["5201", "5202", "5203", "5204", "5205"]
k = np.array(C["kappas"])

fig, ax = plt.subplots(1, 3, figsize=(13, 3.9))

a = ax[0]
a.plot(k, C["h2"]["up"], "-", color="#c33", lw=1.8, label="h = 2: κ вверх")
a.plot(k, C["h2"]["dn"], "--", color="#7b2d8b", lw=1.8, label="h = 2: κ вниз (горячая затравка)")
a.plot(k, C["h1"]["up"], "-", color="#1f5fbf", lw=1.6, label="h = 1: обе ветви совпадают")
a.plot(k, C["h1"]["dn"], ":", color="#1f5fbf", lw=1.2)
a.set_xlabel("κ (сила катализа)"); a.set_ylabel("суммарная масса (СП)")
a.set_title("Граф 5202: кооперативность включает петлю\n(h = 2 — гистерезис; h = 1 — гладкий рост)")
a.legend(fontsize=7)

b = ax[1]
x = np.arange(5)
h2A = [Db[g]["h2"]["A_loop"] for g in GR]
h1A = [Db[g]["h1"]["A_loop"] for g in GR]
b.bar(x - 0.18, h2A, 0.36, color="#c33", label="h = 2")
b.bar(x + 0.18, h1A, 0.36, color="#1f5fbf", label="h = 1 (все = 0.000)")
b.axhline(0.2, color="k", lw=1, ls=":", label="кромка P-P1 = 0.2 (некалибр. к окну ×3)")
b.set_xticks(x); b.set_xticklabels([f"g{g}" for g in GR], fontsize=8)
b.set_ylabel("норм. площадь петли")
b.set_title("Петли: конечные против тождественного нуля\n(по букве P-P1 «не установлен» — кромка, 5-й случай)")
b.legend(fontsize=7)

c = ax[2]
rows = ["двухстартовая\nрасщеплённость (МФ)", "транзиент-серт.\nC1∧C2′", "чередование\nL_alt ≥ 8", "вращение\nL_rot ≥ 8"]
h2v = [5, sum(1 for g in GR if D1[g]["h2_cert"]["fires"]), 0, 0]
h1v = [0, 0, 0, 0]
y = np.arange(len(rows))[::-1]
c.barh(y + 0.18, h2v, 0.36, color="#c33", label="h = 2 (из 5)")
c.barh(y - 0.18, h1v, 0.36, color="#1f5fbf", label="h = 1 (из 5)")
c.set_yticks(y); c.set_yticklabels(rows, fontsize=8)
c.set_xlim(0, 5.5); c.set_xlabel("графов из 5")
c.set_title("Тройка видит только разрывное рождение:\nпри h = 1 молчит всё (P-O2 ✓)")
c.legend(fontsize=8)

fig.suptitle("ORD-001/001b — порядок взаимодействия (кооперативность катализа) переключает ТИП рождения уровня; "
             "непрерывное рождение — слепое пятно тройки, задокументировано", fontsize=10)
fig.tight_layout(rect=[0, 0, 1, 0.9])
fig.savefig("/home/claude/ord001_fig.png", dpi=140)
print("ok")
