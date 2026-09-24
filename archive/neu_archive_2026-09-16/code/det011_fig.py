import json, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

D = json.load(open("/home/claude/det011_results.json"))
RW = sorted(D["win"], key=float)
r = [float(x) for x in RW]
L = [D["win"][x]["L"] for x in RW]
Rl = [D["win"][x]["R_late"] for x in RW]
Re = [D["win"][x]["R_early"] for x in RW]

fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))

a = ax[0]
a.semilogy(r, L, "o-", color="#1f5fbf", label="L_rot (медиана серий Δφ)")
a.axhline(D["LSTAR"], color="#c33", lw=1, ls=":", label=f"L*_rot = {D['LSTAR']:.0f}")
a.axvline(2.0, color="k", lw=0.8, alpha=0.4)
a.axvline(D["rstar"], color="#1f5fbf", lw=1.2, alpha=0.6, label=f"r*_NS = {D['rstar']}")
for x in D["deg"]:
    a.semilogy([float(x)], [D["deg"][x]["L"]], "^", color="#888", ms=7)
a.semilogy([1.45], [D["cross"]["flip"]["L"]], "*", color="#e07b00", ms=13, label="flip r=3.16: L=1")
a.semilogy([1.55], [D["cross"]["fold"]["L"]], "P", color="#7b2d8b", ms=10, label="Шлёгль-фолд: L=1")
a.set_xlabel("r (запаздывающая логистика)"); a.set_ylabel("длина однознаковой серии")
a.set_title("O1′: вращение против вырожденного пола")
a.legend(fontsize=7, loc="upper left")
a.annotate("серия = вся траектория\n(0 проскальзываний)", xy=(2.1, 2000), fontsize=8,
           color="#1f5fbf", ha="center")

b = ax[1]
b.plot(r, Rl, "o-", color="#7b2d8b", label="R_late")
b.plot(r, Re, "s--", color="#bbb", label="R_early")
b.axhline(D["RFLOOR"], color="#c33", lw=1, ls=":", label=f"пол 2×вырожд. = {D['RFLOOR']:.3f}")
b.axvline(2.0, color="k", lw=0.8, alpha=0.4)
b.set_xlabel("r"); b.set_ylabel("радиус от x*")
b.set_title("O2′: удержание радиуса (старт на дет. окружности)")
b.legend(fontsize=7, loc="upper left")

fig.suptitle("DET-011 — NS-сертификат v2: детекция на первой закритической точке (r* = 2.016); "
             "flip и фолд не проходят — три маршрута разделены", fontsize=10)
fig.tight_layout(rect=[0, 0, 1, 0.92])
fig.savefig("/home/claude/det011_fig.png", dpi=140)
print("ok")
