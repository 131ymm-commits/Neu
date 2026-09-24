import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

exec(open("/home/claude/det015_run.py").read().split("t0 = time.time()")[0])

def roots_v1(rec, nb):
    e1 = top_ev(rec, nb, 1); z1 = e1[0]
    return [root_branch(top_ev(rec, nb, lag)[0], lag, z1) for lag in LAGS]

def roots_v3(rec, nb):
    e1 = top_ev(rec, nb, 1)
    z1 = e1[0] if e1[0].imag >= 0 else np.conj(e1[0])
    out = []
    for lag in LAGS:
        lam = top_ev(rec, nb, lag)[0]
        best, bd = None, np.inf
        for L in (lam, np.conj(lam)):
            r_, th = abs(L) ** (1.0 / lag), np.angle(L)
            for k in range(lag):
                z = r_ * np.exp(1j * (th + 2 * np.pi * k) / lag)
                if abs(z - z1) < bd: bd, best = abs(z - z1), z
        out.append(best)
    return out

rec, nb = sim_delayed(2.1036, 320, SEED + 21)
rv1 = roots_v1(rec, nb); rv3 = roots_v3(rec, nb)

D1 = json.load(open("/home/claude/det015_results.json"))
D3 = json.load(open("/home/claude/det015c_results.json"))
EPS = D1["EPS"]

fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.1))

a = ax[0]
th = np.linspace(0, 2 * np.pi, 200)
a.plot(np.cos(th), np.sin(th), "-", color="#ddd", lw=1)
a.scatter([z.real for z in rv1], [z.imag for z in rv1], s=60, marker="x", color="#c33",
          label="v1: ветвь только из λ_est")
a.scatter([z.real for z in rv3], [z.imag for z in rv3], s=40, marker="o", color="#1f5fbf",
          label="v3: ветвь из {λ, λ*}")
for z, lag in zip(rv1, LAGS):
    a.annotate(str(lag), (z.real, z.imag), fontsize=7, color="#c33",
               textcoords="offset points", xytext=(4, 4))
a.set_xlim(0, 1.15); a.set_ylim(-0.2, 1.05)
a.set_aspect("equal")
a.set_xlabel("Re z"); a.set_ylabel("Im z")
a.set_title("NS r = 2.1036: корни по лагам (числа = лаг)")
a.legend(fontsize=8, loc="lower left")

b = ax[1]
cases = ["flip 3.12", "flip 3.16", "flip 3.20", "NS 2.0745", "NS 2.1036", "NS 2.1327",
         "фолд 0.618", "вырожд. NS"]
r1 = [D1["flip"]["3.12"]["rho"], D1["flip"]["3.16"]["rho"], D1["flip"]["3.2"]["rho"],
      D1["ns"]["2.0745"]["rho"], D1["ns"]["2.1036"]["rho"], D1["ns"]["2.1327"]["rho"],
      D1["fold"]["0.618"]["rho"], D1["deg"]["delayed_1.55"]["rho"]]
r3 = [D3["flip"]["3.12"]["reldiff"] * 0 + D1["flip"]["3.12"]["rho"],
      D1["flip"]["3.16"]["rho"], D1["flip"]["3.2"]["rho"],
      D3["ns"]["2.0745"]["rho"], D3["ns"]["2.1036"]["rho"], D3["ns"]["2.1327"]["rho"],
      D1["fold"]["0.618"]["rho"], D3["deg"]["delayed_1.55"]["rho"]]
x = np.arange(len(cases))
b.bar(x - 0.2, r1, 0.4, color="#c33", label="v1", log=True)
b.bar(x + 0.2, r3, 0.4, color="#1f5fbf", label="v3", log=True)
b.axhline(EPS, color="k", lw=1, ls=":", label=f"ε = {EPS:.3f}")
b.set_xticks(x); b.set_xticklabels(cases, rotation=40, ha="right", fontsize=7)
b.set_ylabel("кучность ρ (log)")
b.set_title("Кучность корней: v1 против v3")
b.legend(fontsize=8)

fig.suptitle("DET-015/015b/015c — корне-согласованный оценщик времён: неоднозначность пары разрешена "
             "на уровне корня; flip+NS+фолд закрыты; граница — быстрые моды (t₂ ≪ max lag)", fontsize=9.5)
fig.tight_layout(rect=[0, 0, 1, 0.9])
fig.savefig("/home/claude/det015_fig.png", dpi=140)
print("ok")
