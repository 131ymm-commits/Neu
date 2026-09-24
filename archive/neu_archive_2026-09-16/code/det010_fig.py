import json, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

D = json.load(open("/home/claude/det010_results.json"))
RW = sorted(D["win"], key=float)
r = [float(x) for x in RW]
L = [D["win"][x]["L"] for x in RW]
Ls = [D["win"][x]["L_surr"] for x in RW]
Al = [D["win"][x]["A_late"] for x in RW]
Ae = [D["win"][x]["A_early"] for x in RW]
rat = [D["win"][x]["ratio"] for x in RW]

fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))

a = ax[0]
a.semilogy(r, L, "o-", color="#1f5fbf", label="L (медиана серий)")
a.semilogy(r, Ls, "s--", color="#999", label="L суррогата")
a.axhline(D["LSTAR"], color="#c33", lw=1, ls=":", label=f"L* = {D['LSTAR']:.1f} (вырожд.)")
a.axvline(3.0, color="k", lw=0.8, alpha=0.4)
a.axvline(3.08, color="#2a9d3a", lw=1.2, ls="--", alpha=0.8, label="спектральный r* (DET-003)")
a.axvline(D["rstar"], color="#1f5fbf", lw=1.2, alpha=0.6)
for x in D["deg"]:
    a.semilogy([float(x)], [D["deg"][x]["L"]], "^", color="#888", ms=7)
sch = D["schlogl"]
a.semilogy([2.62], [sch["L"]], "*", color="#e07b00", ms=13,
           label=f"Шлёгль-фолд: L={sch['L']:.0f} (×{sch['ratio']:.1f})")
a.set_xlabel("r"); a.set_ylabel("длина серии чередования")
a.set_title(f"O1: когерентность  →  r* = {D['rstar']}")
a.legend(fontsize=7, loc="upper left")

b = ax[1]
b.plot(r, Al, "o-", color="#7b2d8b", label="A_late")
b.plot(r, Ae, "s--", color="#bbb", label="A_early")
b.axhline(D["AFLOOR"], color="#c33", lw=1, ls=":", label=f"пол 2×вырожд. = {D['AFLOOR']:.3f}")
b.axvline(3.0, color="k", lw=0.8, alpha=0.4)
det = sqrtamp = [np.sqrt(max((x + 1) * (x - 3), 0)) / x if x > 3 else 0 for x in r]
b.plot(r, sqrtamp, "-", color="#2a9d3a", lw=1, alpha=0.6, label="|p−q| детерм.")
b.set_xlabel("r"); b.set_ylabel("|Δx|")
b.set_title("O2: удержание амплитуды (старт на цикле)")
b.legend(fontsize=7, loc="upper left")

c = ax[2]
NW = sorted(D["ns"]["win"], key=float)
nr_ = [float(x) for x in NW]
nL = [D["ns"]["win"][x]["L"] for x in NW]
nLs = [D["ns"]["win"][x]["L_surr"] for x in NW]
c.semilogy(nr_, nL, "o-", color="#1f5fbf", label="L вращения")
c.semilogy(nr_, nLs, "s--", color="#999", label="L суррогата")
c.axvline(2.0, color="k", lw=0.8, alpha=0.4)
c.set_xlabel("r (запазд. логистика)"); c.set_ylabel("длина серии знака Δφ")
c.set_title("P-Y4 (NS): суррогат вырождается — класс B")
c.annotate("однознаковый символ:\nсуррогат ≡ данные,\nотношение слепо", xy=(2.1, 500),
           fontsize=8, color="#c33", ha="center")
c.legend(fontsize=7, loc="lower right")

fig.suptitle("DET-010 — осцилляторный сертификат рождения: O1∧O2 (2 подряд), r* = 3.12; "
             "Шлёгль не проходит; NS-версия требует другой относительной формы", fontsize=10)
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig("/home/claude/det010_fig.png", dpi=140)
print("ok")
