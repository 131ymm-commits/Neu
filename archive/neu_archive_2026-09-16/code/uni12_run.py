"""UNI-12 — psi' across the birth knob (chain length). Per PREREG (frozen 2026-08-31)."""
import json, os, time
import numpy as np
from scipy.stats import spearmanr

exec(open("/home/claude/del001_run.py").read().split("t0 = time.time()")[0])
CK = "/home/claude/uni12_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {}
t0 = time.time()

def sim_multi(k, seed, ntraj=5, broken=False):
    rng = np.random.default_rng(seed)
    n = np.full((ntraj, k), int(round(1.0514 * OMEGA)), dtype=np.int64)
    steps = int(T_TOT / DT); burn = int(T_BURN / DT); stride = int(REC_DT / DT)
    rec = np.empty((ntraj, NS, k))
    ustar = 1.0514 ** H
    bconst = OMEGA * BETA / (1.0 + ustar)
    for i in range(steps):
        if broken:
            b1 = np.full(ntraj, bconst)
        else:
            b1 = OMEGA * BETA / (1.0 + (n[:, -1] / OMEGA) ** H)
        births = np.empty((ntraj, k))
        births[:, 0] = b1
        births[:, 1:] = n[:, :-1]
        n = np.maximum(n + rng.poisson(births * DT) - rng.poisson(n * DT), 0)
        j = i - burn
        if j >= 0 and (j + 1) % stride == 0:
            idx = (j + 1) // stride - 1
            if idx < NS: rec[:, idx, :] = n / OMEGA
    return rec

def gmi(a, b):
    r = float(np.clip(np.corrcoef(a, b)[0, 1], -0.999999, 0.999999))
    return -0.5 * np.log(1 - r * r)

def both_psi(X, M, tau=1):
    v = gmi(M[:-tau], M[tau:])
    xs = [gmi(X[:-tau, j], M[tau:]) for j in range(X.shape[1])]
    return v - sum(xs), v - max(xs)

RNGS = np.random.default_rng(20260835)
for k in list(range(3, 12)) + ["broken"]:
    key = f"k{k}"
    if key in ck: continue
    if k == "broken":
        rec = sim_multi(10, 966010, 5, broken=True)
    else:
        rec = sim_multi(k, 956000 + k, 5)
    ps, pls, surs = [], [], []
    for r in range(5):
        X = rec[r][-8000:]
        if not np.all(np.isfinite(X)) or np.any(X.std(0) == 0):
            print(f"k={k} r={r}: вырожденная реплика — флаг, исключена", flush=True); continue
        M = X.mean(1)
        p, pl = both_psi(X, M)
        Xs = X.copy(); RNGS.shuffle(Xs, axis=0)
        _, pls_s = both_psi(Xs, Xs.mean(1))
        ps.append(p); pls.append(pl); surs.append(pls_s)
    ck[key] = dict(psi=ps, psi_l=pls, sur=surs,
                   med=float(np.median(pls)), med_sur=float(np.median(np.abs(surs))))
    json.dump(ck, open(CK, "w"), default=float)
    print(f"k={k}: ψ′={[round(x,3) for x in pls]} мед={ck[key]['med']:.3f} | ψ={[round(x,2) for x in ps]} | "
          f"|суррогат| мед={ck[key]['med_sur']:.4f} [{time.time()-t0:.0f}s]", flush=True)

KS = list(range(3, 12))
meds = [ck[f"k{k}"]["med"] for k in KS]
rho = float(spearmanr(KS, meds).statistic)
perm = []
R = np.random.default_rng(20260836)
for _ in range(1000):
    perm.append(abs(float(spearmanr(KS, R.permutation(meds)).statistic)))
p_perm = float(np.mean([q >= abs(rho) for q in perm]))
gap = float(np.median([ck[f"k{k}"]["med"] for k in (9, 10, 11)]) - np.median([ck[f"k{k}"]["med"] for k in (3, 4)]))
p1 = rho > 0 and p_perm < 0.05 and gap >= 0.5
p1_kill = rho <= 0 or gap < 0.2
full_range = ck["k11"]["med"] - ck["k3"]["med"]
jump46 = ck["k6"]["med"] - ck["k4"]["med"]
form = "a-скачок" if full_range > 0 and jump46 >= 0.5 * full_range else \
       ("b-докритическая" if ck["k4"]["med"] > ck["k3"]["med"] + 0.1 else "смешанная/плоская")
all_sur = [s for k in KS for s in ck[f"k{k}"]["sur"]]
frac_small = float(np.mean([abs(s) <= 0.05 for s in all_sur]))
p3 = frac_small >= 0.9
p3_kill = float(np.median(np.abs(all_sur))) >= 0.2
p4 = ck["kbroken"]["med"] < ck["k10"]["med"]
loo_sign = all(np.sign(spearmanr(KS, [np.median([x for j, x in enumerate(ck[f'k{k}']['psi_l']) if j != d]) for k in KS]).statistic) > 0 for d in range(5))
ck["verdicts"] = dict(meds={str(k): ck[f"k{k}"]["med"] for k in KS}, rho=rho, p_perm=p_perm, gap=gap,
                      PU121=bool(p1), PU121_killed=bool(p1_kill), form=form, jump46_frac=(jump46 / full_range if full_range else None),
                      frac_sur_small=frac_small, PU123=bool(p3), PU123_killed=bool(p3_kill),
                      broken_med=ck["kbroken"]["med"], k10_med=ck["k10"]["med"], PU124=bool(p4), PU124_killed=bool(not p4),
                      loo_sign=bool(loo_sign))
json.dump(ck, open(CK, "w"), default=float)
print(f"\nмедианы ψ′ по k: {[round(m,3) for m in meds]}")
print(f"P-U12-1: ρ={rho:.3f} (p={p_perm:.3f}), разрыв={gap:.3f} -> {'ПОДТВЕРЖДЁН' if p1 else ('УБИТ' if p1_kill else 'не установлен')} (LOO-знак: {loo_sign})")
print(f"P-U12-2 (вилка): {form} (доля прироста на [4→6]: {ck['verdicts']['jump46_frac']})")
print(f"P-U12-3 (суррогаты малы): {frac_small*100:.0f}% -> {'✓' if p3 else ('УБИТ' if p3_kill else 'не уст.')}")
print(f"P-U12-4 (разорванная {ck['kbroken']['med']:.3f} < k10 {ck['k10']['med']:.3f}): {'ПОДТВЕРЖДЁН' if p4 else 'УБИТ'}")
print(f"[{time.time()-t0:.0f}s]")
