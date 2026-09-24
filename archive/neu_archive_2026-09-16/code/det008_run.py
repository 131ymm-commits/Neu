"""DET-008 — transient protocol for late closures. Per PREREG."""
import json, numpy as np, time, sys

exec(open("/home/claude/det002r_run.py").read().split("import sys, os")[0])  # model + spectral funcs

SEED8 = 20260830
ck = json.load(open("/home/claude/det002r_ckpt.json"))
seeds = {int(k): v for k, v in ck["seeds"].items() if "excluded" not in v}
SILENT = [5006, 5007, 5008, 5012, 5013, 5015, 5018, 5020]
DETECTED = sorted(k for k, v in seeds.items() if v["Kstar"] is not None)

T_TR = 100.0
NTR = 160
STEPS_TR = int(T_TR / DT)
NSAMP_TR = STEPS_TR // REC_EVERY

def simulate_tr(A, M, ntraj, seed, Tt=T_TR):
    steps = int(Tt / DT)
    rng = np.random.default_rng(seed)
    n = rng.poisson(np.full((ntraj, M), EPS)).astype(float)
    rec = np.empty((ntraj, steps // REC_EVERY), dtype=np.int16)
    pdeath = 1 - np.exp(-DT)
    Af = A.astype(float)
    for s in range(steps):
        b = EPS + KAP * (hill(n) @ Af)
        n = np.clip(n + rng.poisson(b * DT) - rng.binomial(n.astype(np.int64), pdeath), 0, NCAP)
        if (s + 1) % REC_EVERY == 0:
            rec[:, (s + 1) // REC_EVERY - 1] = np.clip(n.sum(1), 0, 200)
    return rec  # NO burn-in discard

t0 = time.time()
out = {"silent": {}, "frac_hot": {}}
for sg in SILENT:
    edges = edges_seq(10, sg)
    Kc = seeds[sg]["Kc"]
    Ks = [Kc - 1, Kc, Kc + 1, Kc + 2]
    okr, Rr = {}, {}
    dag_ok = {}
    for K in Ks:
        A = adj_at(edges, 10, K)
        rec = simulate_tr(A, 10, NTR, SEED8 + sg * 10 + K)
        R, ok = crit(rec)
        Rr[K], okr[K] = R, ok
    for K in (Kc, Kc + 1):
        Ad = adj_at(edges, 10, K, dag=True)
        rec = simulate_tr(Ad, 10, NTR, SEED8 + sg * 10 + K + 50)
        _, okd = crit(rec)
        dag_ok[K] = okd
    Kstar = None
    for i in range(len(Ks) - 1):
        if okr.get(Ks[i]) and okr.get(Ks[i + 1]): Kstar = Ks[i]; break
    out["silent"][sg] = dict(Kc=Kc, Rr=Rr, Kstar=Kstar, dag_fired=any(dag_ok.values()))
    print(f"seed {sg}: Kc={Kc} R={ {K: (Rr[K] and round(Rr[K],1)) for K in Ks} } "
          f"K*={Kstar} dag={any(dag_ok.values())} [{time.time()-t0:.0f}s]", flush=True)

# P-S2: frac_hot tail of standard protocol at Kc+1, silent vs detected
def frac_hot_tail(sg):
    edges = edges_seq(10, sg)
    Kc = seeds[sg]["Kc"]
    A = adj_at(edges, 10, Kc + 1)
    rec = simulate_tr(A, 10, 24, SEED8 + 90000 + sg, Tt=400.0)
    tail = rec[:, -int(0.2 * rec.shape[1]):]
    return float((tail > 12).mean())

for sg in SILENT + DETECTED:
    out["frac_hot"][sg] = frac_hot_tail(sg)
print("frac_hot silent:", {s: round(out['frac_hot'][s], 2) for s in SILENT}, flush=True)
print("frac_hot detected:", {s: round(out['frac_hot'][s], 2) for s in DETECTED}, flush=True)

hit = sum(1 for sg in SILENT if out["silent"][sg]["Kstar"] in
          (seeds[sg]["Kc"], seeds[sg]["Kc"] + 1))
dagf = sum(1 for sg in SILENT if out["silent"][sg]["dag_fired"])
print(f"\nP-S1: детекция в {{Kc,Kc+1}} у {hit}/8; DAG {dagf}/8 "
      f"-> {'ПОДТВЕРЖДЁН' if (hit>=6 and dagf==0) else ('УБИТ' if hit<=3 else 'не установлен')}")
sh = sum(1 for s in SILENT if out["frac_hot"][s] >= 0.9)
dh = sum(1 for s in DETECTED if out["frac_hot"][s] <= 0.9)
print(f"P-S2: frac_hot>=0.9 у молчавших {sh}/8; <=0.9 у обнаруженных {dh}/{len(DETECTED)} "
      f"-> {'ПОДТВЕРЖДЁН' if (sh>=6 and dh>=8) else 'не установлен/убит'}")
cal = json.load(open("/home/claude/det008_cal.json"))
from scipy.stats import spearmanr
Ls = [cal[str(s)]["L"] for s in sorted(cal)]
Ts = [cal[str(s)]["tig_med"] for s in sorted(cal)]
rho, pv = spearmanr(Ls, Ts)
print(f"P-S3: Spearman(L_cycle, T_ig) по {len(Ls)} сидам = {rho:.3f} (p={pv:.3f}) "
      f"-> прогноз |rho|<0.5: {'ПОДТВЕРЖДЁН' if abs(rho)<0.5 else 'НЕ подтверждён'}")
json.dump(out, open("/home/claude/det008_results.json", "w"), default=float)
print(f"[{time.time()-t0:.0f}s] -> det008_results.json")
