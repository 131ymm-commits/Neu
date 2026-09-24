import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

D = json.load(open("/home/claude/det014_results.json"))
AW = sorted(D["win"], key=float)
a = [float(x) for x in AW]

fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))

p = ax[0]
S = [D["win"][x].get("S_j16") for x in AW]
p.plot([x for x, s in zip(a, S) if s], [s for s in S if s], "o-", color="#1f5fbf", label="S_j16 = t_wait/t_cross (дж.)")
p.axhline(3, color="#c33", lw=1, ls=":", label="порог S = 3")
p.axvline(2.0, color="k", lw=0.8, alpha=0.5, label="питчфорк a_c = 2")
mono = [x for x in a if D["win"][str(x)].get("struct_silent")]
p.plot(mono, [0.5] * len(mono), "x", color="#999", ms=8, label="моностабильно (структ. молчание)")
p.set_xlabel("a"); p.set_ylabel("S")
p.set_title("C1: активированная структура прохода")
p.legend(fontsize=7, loc="upper left")

q = ax[1]
ph = [D["win"][x].get("p_hot") for x in AW]
pt = [D["win"][x].get("p_twin") for x in AW]
q.plot([x for x, v in zip(a, ph) if v is not None], [v for v in ph if v is not None], "o-",
       color="#7b2d8b", label="p_hot (данные)")
q.plot([x for x, v in zip(a, pt) if v is not None], [v for v in pt if v is not None], "s--",
       color="#e07b00", label="p_twin (разомкнутая петля)")
q.axhline(0.15, color="#c33", lw=1, ls=":", label="p ≥ 0.15")
q.axvline(2.0, color="k", lw=0.8, alpha=0.5)
q.set_xlabel("a"); q.set_ylabel("персистентность")
q.set_title("C2′: самоподдержание против нуль-двойника")
q.legend(fontsize=7)
q.annotate("двойник: v свободен →\nдавит u, p_twin = 0", xy=(2.35, 0.12), fontsize=8,
           color="#e07b00", ha="center")

r = ax[2]
L10 = [D["win"][x].get("L10") for x in AW]
r.plot([x for x, v in zip(a, L10) if v is not None], [v for v in L10 if v is not None], "o-",
       color="#2a9d3a", label="L_rot (stride 10)")
L100 = [D["win"][x].get("L100") for x in AW]
r.plot([x for x, v in zip(a, L100) if v is not None], [v for v in L100 if v is not None], "s--",
       color="#88c999", label="L_rot (stride 100)")
r.axhline(D["LSTAR_ROT"], color="#c33", lw=1, ls=":", label=f"L* = {D['LSTAR_ROT']:.0f}")
r.set_ylim(0, 10)
r.set_xlabel("a"); r.set_ylabel("L_rot")
r.set_title("Кросс: ножка вращения молчит (веществ. моды)")
r.legend(fontsize=7)

fig.suptitle("DET-014 — транзиент-сертификат на тоггле (CME): a* = 2.0909; нуль-двойник обобщён "
             "DAG → разомкнутая петля; тройка разделяет и здесь", fontsize=10)
fig.tight_layout(rect=[0, 0, 1, 0.92])
fig.savefig("/home/claude/det014_fig.png", dpi=140)
print("ok")
