"""PRE-004b — Fano-normalized drift indicators (same trajectories via same seeds). Per PREREG."""
import json
import numpy as np

exec(open("/home/claude/pre004_run.py").read().split("ck = json.load")[0])

def indicators_fano(traj):
    out = []
    for s0 in range(0, NSAMP - W + 1, STRIDE):
        seg = traj[s0:s0 + W]
        x = np.arange(W)
        res = seg - np.polyval(np.polyfit(x, seg, 1), x)
        m = max(seg.mean(), 1e-9)
        f = float(res.var() / m)
        r0 = res[:-LAG]; r1 = res[LAG:]
        ac = float(np.corrcoef(r0, r1)[0, 1]) if res.std() > 0 else 0.0
        out.append((s0 + W // 2, f, ac))
    return out

out = {}
for name, S in SYS.items():
    p0, p1, thr = S["p0"], S["p1"], S["thr"]
    drift = lambda t: p0 + (p1 - p0) * min(t / T_TOT, 1.0)
    const = lambda t: p0
    base = S["sim"](const, SEED + hash(name) % 1000, 5)
    ctrl = S["sim"](const, SEED + hash(name) % 1000 + 77, 5)
    drf = S["sim"](drift, SEED + hash(name) % 1000 + 154, 5)
    ff = fa = -np.inf
    for r in range(5):
        for (_, f, a) in indicators_fano(base[r]):
            ff = max(ff, f); fa = max(fa, a)
    ff *= 2.5; fa = min(2.5 * fa, 0.999)
    fires, leads = 0, []
    for r in range(5):
        w_, c = first_fire(indicators_fano(drf[r]), ff, fa)
        if c is not None and drift(c * REC_DT) < thr:
            fires += 1
            leads.append((thr - drift(c * REC_DT)) / (p1 - p0))
    cf = sum(1 for r in range(5) if first_fire(indicators_fano(ctrl[r]), ff, fa)[1] is not None)
    out[name] = dict(floor_fano=ff, fires=fires, leads=leads, ctrl=cf)
    print(f"{name}: пол Фано={ff:.3g} | до-пороговых {fires}/5 (lead={[round(l,3) for l in leads]}) | "
          f"контроль {cf}/5", flush=True)

ft, f_f, f_h = out["trans"]["fires"], out["fold"]["fires"], out["hopf"]["fires"]
pw1 = "a" if ft >= 4 else ("b" if ft <= 1 else "не установлен")
pw3 = f_h >= 4; pw3_kill = f_h <= 2
pw4_bad = [n for n in SYS if out[n]["ctrl"] >= 2]
out["verdicts"] = dict(PW1=pw1, PW2_fold=f_f, PW3=bool(pw3), PW3_killed=bool(pw3_kill),
                       PW4=len(pw4_bad) == 0, pw4_bad=pw4_bad)
json.dump(out, open("/home/claude/pre004b_results.json", "w"), default=float)
print(f"\nP-W1 (транскритика, Фано): {ft}/5 -> ветвь ({pw1})")
print(f"P-W2 (фолд, запись): {f_f}/5")
print(f"P-W3 (Хопф): {f_h}/5 -> {'ПОДТВЕРЖДЁН' if pw3 else ('УБИТ' if pw3_kill else 'не установлен')}")
print(f"P-W4 (контроли): {'ПОДТВЕРЖДЁН' if not pw4_bad else 'УБИТ: ' + str(pw4_bad)}")
