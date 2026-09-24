"""VER-008b — rate-delay in structural subsets. Per PREREG (frozen 2026-09-01)."""
import json
import numpy as np
from scipy.stats import spearmanr

RNG = np.random.default_rng(20260902)
rows = [r for r in json.load(open("/home/claude/ver008_results.json"))["rows"] if r.get("V_rel") is not None]
A = [r for r in rows if r["V_rel"] <= 2.4]
B = [r for r in rows if r["V_rel"] > 2.4]
for r in B: r["t_hold"] = r["t_rel"] - 2400.0 / r["rate"]
print(f"поднабор (а) во время рампы: {len(A)} файлов; (б) на удержании: {len(B)}")

def test(xs, ys, name):
    rho = float(spearmanr(xs, ys).statistic)
    perm = [abs(float(spearmanr(xs, RNG.permutation(ys)).statistic)) for _ in range(2000)]
    p = float(np.mean([q >= abs(rho) for q in perm]))
    loo = all(np.sign(spearmanr(np.delete(xs, j), np.delete(ys, j)).statistic) == np.sign(rho) for j in range(len(xs)))
    print(f"{name}: ρ = {rho:.3f}, p = {p:.4f}, LOO-знак {loo}")
    return rho, p, loo

res = dict(nA=len(A), nB=len(B))
if len(A) >= 5:
    ra, pa, la = test(np.array([r["rate"] for r in A]), np.array([r["V_rel"] for r in A]), "(а) ρ(V_rel, R)")
    res.update(rho_a=ra, p_a=pa, loo_a=la, med_Vrel_a=float(np.median([r["V_rel"] for r in A])),
               PV8b1=bool(ra > 0 and pa < 0.05), PV8b1_killed=bool(ra <= 0))
if len(B) >= 5:
    rb, pb, lb = test(np.array([r["rate"] for r in B]), np.array([r["t_hold"] for r in B]), "(б) ρ(t_hold, R)")
    res.update(rho_b=rb, p_b=pb, loo_b=lb, t_holds={str(r['rate']): round(r['t_hold'], 2) for r in B},
               PV8b2=bool(rb > 0 and pb < 0.05), PV8b2_killed=bool(rb <= 0))
json.dump(res, open("/home/claude/ver008b_results.json", "w"), default=float)
print(f"якорь EXT-018: медиана V_rel (а) = {res.get('med_Vrel_a')}")
print("P-V8b1:", "ПОДТВЕРЖДЁН" if res.get("PV8b1") else ("УБИТ" if res.get("PV8b1_killed") else "не установлен"),
      "| P-V8b2:", "ПОДТВЕРЖДЁН" if res.get("PV8b2") else ("УБИТ" if res.get("PV8b2_killed") else "не установлен"))
print("-> ver008b_results.json")
