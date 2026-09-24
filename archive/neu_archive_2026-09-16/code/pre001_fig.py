import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ck = json.load(open("/home/claude/pre001_ckpt.json"))
gk = [s for s in ck if s != "verdicts"]

fig, ax = plt.subplots(1, 3, figsize=(13, 3.9))

a = ax[0]
for s in gk:
    e = ck[s]
    if e.get("incomplete"): continue
    Kc = e["Kc"]
    ks = sorted(int(k) for k in e["K"])
    a.plot([k - Kc for k in ks], [e["K"][str(k)]["auc"] for k in ks], "o-", alpha=0.5, lw=1, ms=3)
a.axvline(0, color="#c33", lw=1.2, ls="--")
a.annotate("закрытие\n(рождение уровня)", xy=(-0.15, 0.35), color="#c33", fontsize=8, ha="right")
a.set_xlabel("K − Kc (рёбер до закрытия)")
a.set_ylabel("AUC_p (удержание горячего старта)")
a.set_title("Размягчение до рождения: 17/17 графов растут\n(медиана Спирмена = +1.00)")

b = ax[1]
xs = [ck[s]["sp_data"] for s in gk if not ck[s].get("incomplete")]
ys = [ck[s]["sp_twin"] for s in gk if not ck[s].get("incomplete")]
b.scatter(xs, ys, s=45, color="#1f5fbf", alpha=0.7)
b.plot([0, 1.05], [0, 1.05], "--", color="#999", lw=1)
b.set_xlim(0.4, 1.05); b.set_ylim(0.4, 1.05)
b.set_xlabel("Спирмен(K, AUC) — данные")
b.set_ylabel("Спирмен(K, AUC) — переплетённый двойник")
b.set_title("P-I4 исход (b): двойник размягчается так же —\nпредвестник родовой (уплотнение), Δ = 0.00")

c = ax[2]
def spear(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    rx = np.argsort(np.argsort(x)); ry = np.argsort(np.argsort(y))
    if rx.std() == 0 or ry.std() == 0: return np.nan
    return float(np.corrcoef(rx, ry)[0, 1])
byK = {}
for s in gk:
    Kc = ck[s]["Kc"]
    for k, e in ck[s]["K"].items():
        byK.setdefault(int(k), []).append((Kc - int(k), e["auc"]))
Ks, sps, ns = [], [], []
for k in sorted(byK):
    v = byK[k]
    if len(v) >= 4:
        Ks.append(k); sps.append(spear([d for d, _ in v], [a2 for _, a2 in v])); ns.append(len(v))
c.bar(Ks, sps, color=["#7b2d8b" if s < 0 else "#bbb" for s in sps])
c.axhline(0, color="k", lw=0.8)
for k, s, n in zip(Ks, sps, ns):
    c.annotate(f"n={n}", (k, s), fontsize=6, ha="center",
               va="bottom" if s >= 0 else "top")
c.set_xlabel("K (фиксировано)"); c.set_ylabel("Спирмен(AUC, Kc − K) поперёк графов")
c.set_title("РАЗВЕДКА: расстояние сверх плотности —\nслабо, знако-переменно (медиана −0.20)")

fig.suptitle("PRE-001 — предвестники закрытия каталитического цикла: накопление измеримо (родовое уплотнение), "
             "специфический сигнал близости не установлен", fontsize=10)
fig.tight_layout(rect=[0, 0, 1, 0.91])
fig.savefig("/home/claude/pre001_fig.png", dpi=140)
print("ok")
