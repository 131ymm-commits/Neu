"""LEV-002 analysis per PREREG + figure."""
import json, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

A = json.load(open("/home/claude/lev002_stageA.json"))
B = json.load(open("/home/claude/lev002_stageB.json"))
C = json.load(open("/home/claude/lev002_stageC.json"))
RSTAR = A["RSTAR"]; RLO = RSTAR - 1
KS = list(range(4, 13))

def crit(e):
    return (e["R"] is not None and e["R"] >= RSTAR and e["plateau"]
            and e["j16"] == e["j16"] and e["j16"] >= RLO)

print(f"R* = {RSTAR}  (j16 >= {RLO})")
det = {}
for kind in ("real", "dag"):
    for bn in ("B1", "B2", "B3"):
        ok = [crit(B[kind][str(K)][bn]) for K in KS]
        sust = [ok[i] and ok[i + 1] for i in range(len(ok) - 1)]
        Kstar = KS[sust.index(True)] if any(sust) else None
        det[(kind, bn)] = (ok, Kstar)
        print(f"{kind} {bn}: K*={Kstar}  ok@K={[K for K, o in zip(KS, ok) if o]}")

pre_fired = any(crit(A["preclosure"][str(K)][bn]) for K in (0, 1, 2, 3) for bn in ("B1", "B2", "B3"))
dag_fired = any(det[("dag", bn)][1] is not None or any(det[("dag", bn)][0]) for bn in ("B1", "B2", "B3"))
print(f"\npre-closure fired: {pre_fired};  DAG fired anywhere: {dag_fired}")
p1a = (not pre_fired) and (not dag_fired) and det[("real", "B3")][1] is not None and det[("real", "B3")][1] <= 6
print("P1a:", "ПОДТВЕРЖДЁН" if p1a else "нет", f"(K*_B3={det[('real','B3')][1]})")

# P3 step-likeness on B3
R3 = {int(k): (A["preclosure"][k]["B3"]["R"] or np.nan) for k in A["preclosure"]}
Rw = {K: (B["real"][str(K)]["B3"]["R"] or np.nan) for K in KS}
dR4 = Rw[4] - R3[3]
dRs = [Rw[K] - Rw[K - 1] for K in range(5, 13)]
med = np.nanmedian(np.abs(dRs))
print(f"\nP3: dR(4)={dR4:.2f}; max dR(5..12)={np.nanmax(np.abs(dRs)):.2f}; "
      f"median|dR|={med:.2f}; need dR(4) max & >= {3*med:.2f}")
p3 = dR4 >= 3 * med and dR4 > np.nanmax(np.abs(dRs))
print("P3:", "ПОДТВЕРЖДЁН" if p3 else "нет")

# P2 registered: t2(B2 valid) vs T_hot_ref; fallback B3 (declared)
for bn in ("B2", "B3"):
    ok, Kstar = det[("real", bn)]
    pts = [(K, B["real"][str(K)][bn]["t2"], C[str(K)]["T_hot"])
           for K, o in zip(KS, ok) if o and C[str(K)]["two_state"]]
    if len(pts) >= 3:
        rho, p = spearmanr([p[1] for p in pts], [p[2] for p in pts])
    else:
        rho, p = np.nan, np.nan
    print(f"\nP2 ({bn}): n={len(pts)} rho={rho:.3f} p={p:.3f}")
    print("   (K, t2, T_hot):", [(k, round(a, 1), round(b, 1)) for k, a, b in pts])
    if bn == "B2": p2_primary = (len(pts), rho)

# exploratory (NOT preregistered): t2 vs exchange time
pts = [(K, B["real"][str(K)]["B3"]["t2"],
        1 / (1 / C[str(K)]["T_hot"] + 1 / C[str(K)]["T_dark"]))
       for K in KS if C[str(K)]["two_state"] and B["real"][str(K)]["B3"]["t2"]]
rho_e, p_e = spearmanr([p[1] for p in pts], [p[2] for p in pts])
print(f"\nEXPLORATORY (вне предрегистрации): t2(B3) vs t_exch: n={len(pts)} rho={rho_e:.3f} p={p_e:.4f}")
print("   pairs:", [(k, round(a, 1), round(b, 1)) for k, a, b in pts])

print("\nSurrogates:", B["surr"])
print("Conv @K=8:", B["conv"]["pts"])

# ---------- figure ----------
fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
ax = axes[0]
allK = [0, 1, 2, 3] + KS
Rr = [R3.get(K, np.nan) for K in (0, 1, 2, 3)] + [Rw[K] for K in KS]
Rd = [np.nan] * 4 + [B["dag"][str(K)]["B3"]["R"] or np.nan for K in KS]
ax.plot(allK, Rr, "-o", color="tab:green", label="реальный граф (B3)")
ax.plot(allK, Rd, "-s", color="tab:gray", label="DAG-контроль (B3)")
for bn, c in (("B1", "#cccccc"), ("B2", "tab:orange")):
    ax.plot(KS, [B["real"][str(K)][bn]["R"] or np.nan for K in KS], "-o", ms=3, color=c, alpha=0.8, label=f"реальный ({bn})")
ax.axhline(RSTAR, color="k", ls=":", lw=1, label=f"R*={RSTAR:.1f}")
ax.axvline(4, color="k", ls="--", lw=1)
ax.text(4.06, 0.4, "закрытие цикла (K=4)", rotation=90, fontsize=8)
ax.set_xlabel("K (число рёбер катализа)"); ax.set_ylabel("R = t2/t3")
ax.set_title("Ступень при закрытии; DAG равной плотности молчит")
ax.legend(fontsize=7)

ax = axes[1]
Kc = [int(k) for k in C]
ax.semilogy(Kc, [C[str(K)]["T_dark"] for K in Kc], "-o", label="T_dark (референс)")
ax.semilogy(Kc, [C[str(K)]["T_hot"] for K in Kc], "-s", label="T_hot (референс)")
ax.semilogy(KS, [B["real"][str(K)]["B3"]["t2"] or np.nan for K in KS], "-^", label="t2 эмпир. (B3)")
ax.axvline(4, color="k", ls="--", lw=1)
ax.set_xlabel("K"); ax.set_ylabel("время, ед.")
ax.set_title("Времена: рождение при K=4; жизни почти не зависят от K")
ax.legend(fontsize=8)

ax = axes[2]
x = [p[1] for p in pts]; y = [p[2] for p in pts]
ax.scatter(x, y, s=45, color="tab:purple")
for (k, a, b) in pts:
    ax.annotate(str(k), (a, b), fontsize=7, xytext=(3, 3), textcoords="offset points")
ax.set_xlabel("t2 эмпир. (B3)"); ax.set_ylabel("t_exch референс")
ax.set_title(f"Эксплораторно (вне PREREG): ρ={rho_e:.2f}, n={len(pts)}")
fig.suptitle("LEV-002: рождение уровня замыканием (первый цикл катализа) и спектральный детектор", fontsize=11)
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig("/home/claude/lev002_fig.png", dpi=140)
print("\nfig -> lev002_fig.png")
