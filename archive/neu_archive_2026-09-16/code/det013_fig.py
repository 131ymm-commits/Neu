import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

D = json.load(open("/home/claude/det013_results.json"))
Db = json.load(open("/home/claude/det012b_results.json"))
BW = sorted(Db["win"], key=float)
b = [float(x) for x in BW]

fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.9))

a = ax[0]
cols = {"500": "#999", "2000": "#1f5fbf", "8000": "#c33"}
a.semilogy(b, [Db["win"][x]["L_rot"] for x in BW], "s--", color=cols["500"], label="Ω = 500 (DET-012b)")
for OM in ("2000", "8000"):
    o = D[OM]
    a.semilogy(b, [o["win"][x]["L_rot"] for x in BW], "o-", color=cols[OM], label=f"Ω = {OM}")
a.axhline(8, color="k", lw=1, ls=":", label="L* = 8")
a.axvline(5.0, color="k", lw=0.8, alpha=0.5)
a.set_xlabel("b"); a.set_ylabel("L_rot")
a.set_title("Когерентность вращения при трёх Ω")
a.legend(fontsize=7, loc="upper left")

c = ax[1]
oms = [500, 2000, 8000]
bd = [Db["bstar"], D["2000"]["bstar"], D["8000"]["bstar"]]
lag = [x - 5.0 if x else None for x in bd]
c.loglog(oms, lag, "o-", color="#1f5fbf", label="Δb = b_det − 5.0")
ref = [lag[0] * (500 / om) for om in oms]
c.loglog(oms, ref, "--", color="#888", label="Ω⁻¹ (γ = 1)")
ref2 = [lag[0] * (500 / om) ** 0.5 for om in oms]
c.loglog(oms, ref2, ":", color="#bbb", label="Ω^{-1/2}")
c.set_xlabel("Ω"); c.set_ylabel("запаздывание Δb")
c.set_title("Масштабирование запаздывания детекции")
c.legend(fontsize=8)

fig.suptitle("DET-013 — запаздывание траекторной детекции у Хопфа: шум или конструкция?", fontsize=10)
fig.tight_layout(rect=[0, 0, 1, 0.92])
fig.savefig("/home/claude/det013_fig.png", dpi=140)
print("ok")
