import json, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

Da = json.load(open("/home/claude/det012_results.json"))
Db = json.load(open("/home/claude/det012b_results.json"))
BW = sorted(Da["win"], key=float)
b = [float(x) for x in BW]

fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))

a = ax[0]
La = [Da["win"][x]["L_rot"] for x in BW]
a.plot(b, La, "o-", color="#c33", label="L_rot при Δt_s = период/63")
a.axhline(Da["LSTAR_ROT"], color="#c33", lw=1, ls=":", label="L*_rot = 8")
a.axvline(5.0, color="k", lw=0.8, alpha=0.5)
a.set_ylim(0, 10)
a.set_xlabel("b"); a.set_ylabel("L_rot")
a.set_title("Часть A: ножка когерентности мертва\n(ω·Δt_s = 0.1 — шаг утонул в шуме)")
a.legend(fontsize=7, loc="upper left")
a.annotate("убийца линии:\nдетекции нет нигде,\nдаже при R ≈ 2.9", xy=(5.6, 5.5),
           fontsize=8, color="#c33", ha="center")

c = ax[1]
Rl = [Da["win"][x]["R_late"] for x in BW]
c.plot(b, Rl, "s-", color="#7b2d8b", label="R_late (интенсивная ножка)")
c.axhline(Da["RFLOOR"], color="#c33", lw=1, ls=":", label=f"пол = {Da['RFLOOR']:.2f}")
c.axvline(5.0, color="k", lw=0.8, alpha=0.5)
for x in Da["deg"]:
    c.plot([float(x)], [Da["deg"][x]["R_late"]], "^", color="#888", ms=7)
c.set_xlabel("b"); c.set_ylabel("радиус")
c.set_title("Радиус: гладкий рост ЧЕРЕЗ порог —\nразмытие Хопфа квазициклами (Ω = 500)")
c.legend(fontsize=7, loc="upper left")
c.annotate("вспыхивает ниже порога\n(квазицикловое раздувание) —\nконъюнкция гасит", xy=(4.85, 1.9),
           fontsize=8, color="#7b2d8b", ha="center")

d = ax[2]
Lb = [Db["win"][x]["L_rot"] for x in BW]
d.semilogy(b, Lb, "o-", color="#1f5fbf", label="L_rot при ω·Δt_s = 1")
d.axhline(Db["LSTAR_ROT"], color="#c33", lw=1, ls=":", label="L*_rot = 8")
d.axvline(5.0, color="k", lw=0.8, alpha=0.5, label="Хопф b* = 5")
d.axvline(Db["bstar"], color="#1f5fbf", lw=1.2, alpha=0.6, label=f"детекция b = {Db['bstar']}")
for x in Db["deg"]:
    d.semilogy([float(x)], [Db["deg"][x]["L_rot"]], "^", color="#888", ms=7)
d.set_xlabel("b"); d.set_ylabel("L_rot")
d.set_title("Часть B: явное правило ω·Δt_s ≈ 1 —\nперенос подтверждён (посл. допустимый узел)")
d.legend(fontsize=7, loc="upper left")

fig.suptitle("DET-012/012b — перенос тройки сертификатов на стохастический Брюсселятор (CME, Хопф): "
             "скрытое допущение вскрыто → правило дискретизации → детекция b* = 5.47", fontsize=10)
fig.tight_layout(rect=[0, 0, 1, 0.92])
fig.savefig("/home/claude/det012_fig.png", dpi=140)
print("ok")
