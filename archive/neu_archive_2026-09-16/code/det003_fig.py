import json, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

D = json.load(open("/home/claude/det003_results.json"))
O = json.load(open("/home/claude/ol001_results.json"))
fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))

# --- OL-001 panel ---
ax = axes[0]
orgs = ["iIT341", "iAF692", "iND750", "iNJ661"]
xs = np.arange(len(orgs))
fc = [O[o]["f_cur"] for o in orgs]
fs = [O[o]["f_skel"] for o in orgs]
q50 = [O[o]["deg_null_q50"] for o in orgs]
q95 = [O[o]["deg_null_q95"] for o in orgs]
ax.bar(xs - 0.2, fc, 0.4, label="валюты (орг.)", color="tab:purple")
ax.bar(xs + 0.2, fs, 0.4, label="каркас (орг.)", color="#bbbbbb")
ax.plot(xs, q50, "k_", ms=22, label="q50 нуля по степени")
ax.plot(xs, q95, "r_", ms=22, label="q95 нуля по степени")
ax.set_xticks(xs); ax.set_xticklabels(["H.pyl", "M.bark", "дрожжи", "M.tb"])
ax.set_ylabel("доля нуклеотидной метки")
ax.set_title("OL-001: метку объясняет СТЕПЕНЬ\n(валюты ≤ q50 степень-нуля в 3/4) — P-O1 убит")
ax.legend(fontsize=7)

# --- DET-003 Rc(r) ---
ax = axes[1]
rw = sorted(float(k) for k in D["win"])
for bn, c in (("B1", "#bbbbbb"), ("B2", "tab:orange"), ("B3", "tab:green")):
    ax.semilogy(rw, [D["win"][str(r)][bn]["Rc"] or np.nan for r in rw], "-o", ms=3, color=c, label=bn)
rd = sorted(float(k) for k in D["deg"])
ax.semilogy(rd, [D["deg"][str(r)]["B3"]["Rc"] for r in rd], "s", color="tab:blue", label="вырожд. (B3)")
ax.axhline(D["RSTAR"], color="k", ls=":", lw=1, label=f"R*={D['RSTAR']:.1f}")
ax.axvline(3.0, color="k", ls="--", lw=1)
ax.text(3.005, 1.3, "r₁=3.0 (флип)", rotation=90, fontsize=8)
ax.axvline(3.08, color="tab:green", ls="--", lw=1)
ax.set_xlabel("r"); ax.set_ylabel("R_c = t2/t3 (по |λ|)")
ax.set_title("DET-003: рождение 2-цикла — детекция с r=3.08\n(несимметризованный оценщик)")
ax.legend(fontsize=7)

# --- angle classification ---
ax = axes[2]
th_flip = [D["win"][str(r)]["B3"]["theta1"] / np.pi for r in rw]
ax.plot(rw, th_flip, "-o", ms=4, color="tab:red", label="флип: θ(лаг1)/π")
fr_keys = sorted(float(k) for k in D["fold"])
ax.plot([2.6 + 0.1 * i for i in range(len(fr_keys))],
        [D["fold"][str(f)]["1"]["th"] / np.pi if "1" in D["fold"][str(f)] else D["fold"][str(f)][1]["th"] / np.pi for f in fr_keys],
        "s", ms=8, color="tab:blue", label="фолд-компаратор (Шлёгль)")
ax.axhline(1.0, color="tab:red", ls=":", lw=1)
ax.axhline(0.0, color="tab:blue", ls=":", lw=1)
ax.fill_between([2.55, 3.45], 0.75, 1.25, color="tab:red", alpha=0.08)
ax.fill_between([2.55, 3.45], -0.25, 0.25, color="tab:blue", alpha=0.08)
ax.set_ylim(-0.4, 1.4); ax.set_xlim(2.55, 3.45)
ax.set_xlabel("r (флип) / позиция (фолд)")
ax.set_ylabel("θ/π отделяющейся моды")
ax.set_title("Угол классифицирует маршрут: 6/6\n(флип θ≈π, фолд θ≈0)")
ax.legend(fontsize=8)

fig.suptitle("OL-001 (химия: метка и ярусы) + DET-003 (угол моды как отпечаток механизма)", fontsize=11)
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig("/home/claude/ol001_det003_fig.png", dpi=140)
print("fig saved")
