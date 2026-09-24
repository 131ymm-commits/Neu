"""PRE-005b — extensive-CME Schlogl tau-leap; B/N-tipping on correct clocks. Per PREREG."""
import json, os, sys, time
import numpy as np

SEED = 20260854
T_TOT = 2400.0
REC_DT = 0.1
NSAMP = int(T_TOT / REC_DT)
W = 500
STRIDE = 100
LAG = 10
DT = 0.005
CKPT = "/home/claude/pre005b_ckpt.json"
P0, P1, THR = 0.30, 1.10, 1.00
k1s, k4s = 5.75, 8.75
SN1, Ww = 1.37154, 4.00578 - 1.37154

def sim_ext(par_fn, seed, ntraj, V):
    rng = np.random.default_rng(seed)
    fr0 = par_fn(0.0)
    k30 = SN1 + fr0 * Ww
    rts = np.roots([-1.0, k1s, -k4s, k30]); rts = np.sort(rts[np.isreal(rts)].real)
    n = np.full(ntraj, int(round(V * rts[0])), dtype=np.int64)
    steps = int(T_TOT / DT)
    stride = int(REC_DT / DT)
    rec = np.empty((ntraj, NSAMP))
    for i in range(steps):
        fr = par_fn(i * DT)
        k3 = SN1 + fr * Ww
        x = n / V
        bp = V * (k3 + k1s * x * x)
        bm = V * (k4s * x + x ** 3)
        n = np.maximum(n + rng.poisson(bp * DT) - rng.poisson(bm * DT), 0)
        if (i + 1) % stride == 0:
            k = (i + 1) // stride - 1
            if k < NSAMP: rec[:, k] = n / V
    return rec

def indicators(traj):
    out = []
    for s0 in range(0, NSAMP - W + 1, STRIDE):
        seg = traj[s0:s0 + W]
        x = np.arange(W)
        res = seg - np.polyval(np.polyfit(x, seg, 1), x)
        v = float(res.var())
        r0 = res[:-LAG]; r1 = res[LAG:]
        ac = float(np.corrcoef(r0, r1)[0, 1]) if res.std() > 0 else 0.0
        out.append((s0 + W // 2, v, ac))
    return out

def first_fire(ind, fv, fa):
    hv = [c for j, (c, v, a) in enumerate(ind[:-1]) if v >= fv and ind[j + 1][1] >= fv]
    ha = [c for j, (c, v, a) in enumerate(ind[:-1]) if a >= fa and ind[j + 1][2] >= fa]
    cands = ([("var", hv[0])] if hv else []) + ([("ac1", ha[0])] if ha else [])
    if not cands: return None, None
    w_, c = min(cands, key=lambda t: t[1])
    return w_, c

drift = lambda t: P0 + (P1 - P0) * min(t / T_TOT, 1.0)
const = lambda t: P0

ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
t0 = time.time()
arg = sys.argv[1] if len(sys.argv) > 1 else "all"

for V in (20, 200):
    key = f"V{V}"
    if key in ck: continue
    if arg != "all" and arg != str(V): continue
    base = sim_ext(const, SEED + V, 5, V)
    ctrl = sim_ext(const, SEED + V + 77, 5, V)
    drf = sim_ext(drift, SEED + V + 154, 5, V)
    allv, alla = [], []
    for r in range(5):
        for (_, v, a) in indicators(base[r]):
            allv.append(v); alla.append(a)
    fv = 2.5 * float(np.percentile(allv, 99))
    fa = min(2.5 * float(np.percentile(alla, 99)), 0.999)
    fires, leads, trans_fr = 0, [], []
    for r in range(5):
        tr = drf[r]
        cross = np.flatnonzero(tr > 2.2)
        trans_fr.append(float(drift(cross[0] * REC_DT)) if cross.size else None)
        w_, c = first_fire(indicators(tr), fv, fa)
        if c is not None and drift(c * REC_DT) < THR:
            fires += 1
            leads.append(float(THR - drift(c * REC_DT)))
    cf = sum(1 for r in range(5) if first_fire(indicators(ctrl[r]), fv, fa)[1] is not None)
    ck[key] = dict(floor_var=fv, floor_ac=fa, fires=fires, leads=leads,
                   trans_fr=trans_fr, ctrl=cf)
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"V={V}: переходы при fr={[(round(x,3) if x else None) for x in trans_fr]} | "
          f"до-пороговых {fires}/5 (lead={[round(l,3) for l in leads]}) | контроль {cf}/5 "
          f"[{time.time()-t0:.0f}s]", flush=True)

if all(f"V{V}" in ck for V in (20, 200)):
    tf200 = [x for x in ck["V200"]["trans_fr"] if x is not None]
    n1 = sum(1 for x in tf200 if x >= 0.9)
    bu1 = n1 >= 4; bu1_kill = n1 <= 2
    f200 = ck["V200"]["fires"]
    bu2 = f200 >= 4; bu2_kill = bu1 and f200 <= 2
    tf20 = [x for x in ck["V20"]["trans_fr"] if x is not None]
    n3 = sum(1 for x in tf20 if x < 0.9)
    bu3 = n3 >= 4
    bu4_bad = [V for V in (20, 200) if ck[f"V{V}"]["ctrl"] >= 2]
    ck["verdicts"] = dict(PBU1=bool(bu1), PBU1_killed=bool(bu1_kill), PBU2=bool(bu2),
                          PBU2_killed=bool(bu2_kill), PBU3=bool(bu3), PBU4=len(bu4_bad) == 0)
    json.dump(ck, open(CKPT, "w"), default=float)
    print(f"\nP-BU1 (B-режим при V=200): {n1}/5 при fr>=0.9 -> "
          f"{'ПОДТВЕРЖДЁН' if bu1 else ('УБИТ' if bu1_kill else 'не установлен')}")
    print(f"P-BU2 (CSD жив в B-режиме): {f200}/5 -> "
          f"{'ПОДТВЕРЖДЁН' if bu2 else ('УБИТ' if bu2_kill else 'не установлен')} "
          f"(lead={[round(l,3) for l in ck['V200']['leads']]})")
    print(f"P-BU3 (N-режим при V=20): {n3}/5 ранних -> {'ПОДТВЕРЖДЁН' if bu3 else 'нет'}")
    print(f"P-BU4 (контроли): {'ПОДТВЕРЖДЁН' if not bu4_bad else 'УБИТ: ' + str(bu4_bad)}")
print(f"[{time.time()-t0:.0f}s]")
