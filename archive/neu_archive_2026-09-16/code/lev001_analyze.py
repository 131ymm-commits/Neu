"""LEV-001 analysis strictly per PREREG criteria + figures."""
import json, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

D = json.load(open("/home/claude/lev001_results.json"))
RSTAR = {20: 5.5, 30: 7.5}
FR = np.array(D["meta"]["FR_GRID"])

def detections(V, bn):
    g = D["results"][str(V)]["grid"]
    ok = []
    for e in g:
        b = e["budgets"][bn]
        crit = (b["R"] is not None and b["R"] >= RSTAR[V] and b["plateau"]
                and b["j16"] is not None and not np.isnan(b["j16"]) and b["j16"] >= RSTAR[V] - 1)
        ok.append(bool(crit))
    ok = np.array(ok)
    sust = ok[:-1] & ok[1:]
    mu = FR[:-1][sust]
    return ok, (float(mu[0]) if len(mu) else None)

def bim_detections(V, bn):
    g = D["results"][str(V)]["grid"]
    ok = np.array([e["budgets"][bn]["bimodal"] for e in g])
    sust = ok[:-1] & ok[1:]
    mu = FR[:-1][sust]
    return ok, (float(mu[0]) if len(mu) else None)

print("=== Детекции по полным критериям PREREG (R>=R*, плато, j16>=R*-1, 2 подряд) ===")
combos = []
for V in (20, 30):
    for bn in ("B1", "B2", "B3"):
        okS, muS = detections(V, bn)
        okB, muB = bim_detections(V, bn)
        combos.append((V, bn, muS, muB))
        print(f"V={V} {bn}: mu*_spec={muS}  mu*_bim={muB}  "
              f"spec_pts={[f'{FR[i]:+.3f}' for i in np.where(okS)[0]]}")

step = float(FR[1] - FR[0])
earlier = later = equal = excluded = 0
for V, bn, muS, muB in combos:
    if muS is None and muB is None: excluded += 1; continue
    if muS is None: later += 1; continue
    if muB is None: earlier += 1; continue
    if muS <= muB - step * 0.999: earlier += 1
    elif muS > muB + 1e-9: later += 1
    else: equal += 1
print(f"\nP1: earlier={earlier} equal={equal} later={later} excluded={excluded} (нужно: >=4 earlier, 0 later)")
p1 = "P1a ПОДТВЕРЖДЁН" if (earlier >= 4 and later == 0) else \
     ("P1b ПОДТВЕРЖДЁН" if later >= 3 else "INCONCLUSIVE")
print(p1)

# P2: valid spectral detection points at B2 (primary), birth side T_hl<T_lh
xs, ys, tags = [], [], []
for V in (20, 30):
    okS, muS = detections(V, "B2")
    g = D["results"][str(V)]["grid"]
    if muS is None: continue
    started = False
    for i, e in enumerate(g):
        if not okS[i]: continue
        if float(e["fr"]) < muS: continue
        ex = e["exact"]
        if "T_hl" not in ex or "T_lh" not in ex: continue
        if not (ex["T_hl"] < ex["T_lh"]): continue
        b = e["budgets"]["B2"]
        if b["t2"] is None: continue
        xs.append(b["t2"]); ys.append(ex["T_hl"]); tags.append((V, float(e["fr"])))
rho, pval = spearmanr(xs, ys) if len(xs) >= 3 else (np.nan, np.nan)
print(f"\nP2: n={len(xs)} точек (B2, обе V, сторона рождения); Spearman rho={rho:.3f} (p={pval:.3g})")
print("   пары (t2_emp, T_hl_exact):", [(round(a,1), round(b,1)) for a, b in zip(xs, ys)])
p2 = "P2 ПОДТВЕРЖДЁН (rho>=0.8)" if rho >= 0.8 else ("P2 УБИТ (rho<0.5)" if rho < 0.5 else "P2 слабо/не установлено")
print(p2)

# controls summary
print("\n=== Контроли ===")
for V in (20, 30):
    degR = [b["R"] for e in D["results"][str(V)]["deg"] for b in e["budgets"].values() if b["R"]]
    print(f"V={V} вырожденные: max R = {max(degR):.2f} (порог {RSTAR[V]}) -> {'OK' if max(degR) < RSTAR[V] else 'ПРОВАЛ'}")
    for s in D["results"][str(V)]["surr"]:
        trig = s["R"] is not None and s["R"] >= RSTAR[V]
        print(f"V={V} суррогат fr={s['fr']:+.3f}: R={s['R'] and round(s['R'],2)} t2={s['t2'] and round(s['t2'],1)} "
              f"bim={s['bimodal']} -> spec {'СРАБОТАЛ (ПРОВАЛ)' if trig else 'молчит (OK)'}")

# ---------- figures ----------
fig, axes = plt.subplots(2, 2, figsize=(13, 9.5))
exact = {V: dict(fr=[], R=[], Thl=[], Tlh=[], pk=[]) for V in (20, 30)}
for V in (20, 30):
    for e in D["results"][str(V)]["grid"]:
        ex = e["exact"]
        exact[V]["fr"].append(e["fr"]); exact[V]["R"].append(ex["R"])
        exact[V]["Thl"].append(ex.get("T_hl", np.nan)); exact[V]["Tlh"].append(ex.get("T_lh", np.nan))
        exact[V]["pk"].append(ex["pi_peaks"])

ax = axes[0, 0]
for V, c in ((20, "tab:blue"), (30, "tab:red")):
    ax.plot(exact[V]["fr"], exact[V]["R"], "-o", ms=3, color=c, label=f"exact R, V={V}")
    ax.axhline(RSTAR[V], color=c, ls=":", lw=1)
    degR = [b["R"] for e in D["results"][str(V)]["deg"] for b in e["budgets"].values() if b["R"]]
    ax.scatter([-0.45]*len(degR), degR, color=c, marker="x", s=20)
ax.axvline(0, color="k", lw=1, ls="--"); ax.text(0.005, 0.5, "SN1", rotation=90, fontsize=8)
for V, c in ((20, "tab:blue"), (30, "tab:red")):
    pk2 = [f for f, p in zip(exact[V]["fr"], exact[V]["pk"]) if p >= 2]
    if pk2: ax.axvline(min(pk2), color=c, lw=1, ls="-.", alpha=0.6)
ax.set_xlabel("fr = (k3−SN1)/W"); ax.set_ylabel("R = t2/t3")
ax.set_title("Точный расчёт: R и пороги; ×-ы = вырожденный контроль\n(штрихпунктир — точная бимодальность π)")
ax.legend(fontsize=8)

for col, V in ((0, 20), (1, 30)):
    ax = axes[1, col]
    g = D["results"][str(V)]["grid"]
    for bn, c in (("B1", "#bbbbbb"), ("B2", "tab:orange"), ("B3", "tab:green")):
        R = [e["budgets"][bn]["R"] or np.nan for e in g]
        j16 = [e["budgets"][bn]["j16"] for e in g]
        j84 = [e["budgets"][bn]["j84"] for e in g]
        ax.plot(FR, R, "-o", ms=3, color=c, label=bn)
        ax.fill_between(FR, j16, j84, color=c, alpha=0.15)
        okS, muS = detections(V, bn)
        if muS is not None:
            ax.axvline(muS, color=c, ls="--", lw=1.2)
        okB, muB = bim_detections(V, bn)
        if muB is not None:
            ax.axvline(muB, color=c, ls=":", lw=2.4, alpha=0.8)
    ax.axhline(RSTAR[V], color="k", ls=":", lw=1)
    ax.axvline(0, color="k", lw=1, ls="--")
    ax.set_ylim(0, 15 if V == 30 else 10)
    ax.set_xlabel("fr"); ax.set_ylabel("R эмпир.")
    ax.set_title(f"V={V}: эмпирический R по бюджетам\n(-- μ*_spec, ⋯ μ*_bim)")
    ax.legend(fontsize=8)

ax = axes[0, 1]
mk = {20: "o", 30: "s"}
for (V, fr), x, y in zip(tags, xs, ys):
    ax.scatter(x, y, marker=mk[V], s=40,
               color="tab:blue" if V == 20 else "tab:red")
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("t2 эмпир. (B2)"); ax.set_ylabel("точное T_hl (жизнь нового уровня)")
ax.set_title(f"P2: щель → время жизни; Spearman ρ={rho:.2f} (n={len(xs)})\n(круги V=20, квадраты V=30)")
fig.suptitle("LEV-001: отделение медленной моды как детектор рождения уровня (модель Шлёгля)", fontsize=12)
fig.tight_layout(rect=[0, 0, 1, 0.97])
fig.savefig("/home/claude/lev001_fig.png", dpi=140)
print("\nfig -> lev001_fig.png")
