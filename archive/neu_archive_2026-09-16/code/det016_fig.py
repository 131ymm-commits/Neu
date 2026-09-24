import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ck = json.load(open("/home/claude/det016_ckpt.json"))
e = ck["g5202"]["h1"]
ks = np.array(e["ks"])

fig, ax = plt.subplots(1, 3, figsize=(13, 3.9))

a = ax[0]
a.plot(ks, e["M"], "o-", color="#1f5fbf", label="данные (цикл, h = 1)")
a.plot(ks, e["Mt"], "s--", color="#999", label="DAG-двойник")
a.axvline(ck["g5202"]["kc_mf"], color="k", lw=0.8, ls=":", label=f"κ_c^MF = {ck['g5202']['kc_mf']:.1f}")
a.set_xlabel("κ"); a.set_ylabel("стационарная масса")
a.set_title("g5202: излом есть, но ε-скруглён\n(вторые разности тонут в шуме)")
a.legend(fontsize=8)

b = ax[1]
b.plot(ks, e["F"], "o-", color="#7b2d8b", label="фактор Фано (данные)")
b.plot(ks, e["Ft"], "s--", color="#999", label="фактор Фано (двойник)")
b.set_xlabel("κ"); b.set_ylabel("V/M")
b.set_title(f"Пик флуктуаций скромен: Rv = {e['Rv']:.2f}\nпри поле {ck['stageA']['floor_v']:.2f}")
b.legend(fontsize=8)

c = ax[2]
GR = ["5201", "5202", "5203", "5204", "5205"]
Rc = [ck[f"g{g}"]["h1"]["Rc"] for g in GR]
Rv = [ck[f"g{g}"]["h1"]["Rv"] for g in GR]
x = np.arange(5)
c.bar(x - 0.18, Rc, 0.36, color="#1f5fbf", label="Rc (излом)")
c.bar(x + 0.18, Rv, 0.36, color="#7b2d8b", label="Rv (Фано)")
c.axhline(ck["stageA"]["floor_c"], color="#1f5fbf", lw=1, ls=":", label=f"пол_c = {ck['stageA']['floor_c']:.1f}")
c.axhline(ck["stageA"]["floor_v"], color="#7b2d8b", lw=1, ls=":", label=f"пол_v = {ck['stageA']['floor_v']:.1f}")
c.set_xticks(x); c.set_xticklabels([f"g{g}" for g in GR], fontsize=8)
c.set_ylabel("отношение к двойнику")
c.set_title("P-Q1 УБИТ 0/5: сигнал под полами\n(H0: ε-скругление + шумо-хрупкая статистика)")
c.legend(fontsize=7)

fig.suptitle("DET-016 v1 — сертификат непрерывного рождения: убит собственным убийцей; ножка непрерывности "
             "работает (h = 2 отвергнут 5/5), нильпотентная плоскость вырожденных точна; слепое пятно открыто", fontsize=9.5)
fig.tight_layout(rect=[0, 0, 1, 0.9])
fig.savefig("/home/claude/det016_fig.png", dpi=140)
print("ok")
