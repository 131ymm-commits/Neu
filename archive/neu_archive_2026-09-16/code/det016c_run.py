"""DET-016c — v3: drop dead Fano leg. h1 from frozen v2 ckpt; h2 rerun with identical seeds, full storage."""
import json, sys, os, time
import numpy as np

exec(open("/home/claude/det016b_run.py").read().split("ck = json.load")[0])  # reuse all machinery/constants

ckb = json.load(open("/home/claude/det016b_ckpt.json"))
FL = ckb["floors"]
CKPT3 = "/home/claude/det016c_ckpt.json"
ck3 = json.load(open(CKPT3)) if os.path.exists(CKPT3) else {}
t0 = time.time()
arg = sys.argv[1] if len(sys.argv) > 1 else "all"

def v3_rule(Rc, split, interior, kbp, kf, dk):
    return bool(Rc >= FL["floor_c"] and not split and interior and abs(kbp - kf) <= 3 * dk + 1e-9)

for sg in CYC:
    key = f"g{sg}"
    if key in ck3: continue
    if arg != "all" and arg != str(sg): continue
    e2 = ckb[key]
    ks = np.array(e2["ks"]); dk = ks[1] - ks[0]
    # h1 verdict from frozen v2 data
    f_h1 = v3_rule(e2["Rc"], e2["split"], e2["interior"], e2["kbp"], e2["kf"], dk)
    # h2 rerun (identical seeds as v2) with full evaluation of v3 rule
    edges = edges_seq(M, sg)
    A = adj_at(edges, M, k_cycle(edges, M))
    Ad = adj_at(edges, M, k_cycle(edges, M), dag=True)
    kf2 = prescan_kf(A, 20.0, h2, SEED + sg * 3 + 7)
    ks2 = np.linspace(0.5 * kf2, 1.6 * kf2, NK)
    dk2 = ks2[1] - ks2[0]
    Md2, Fd2 = curves(A, ks2, h2, SEED + sg * 3 + 8)
    Mt2, Ft2 = curves(Ad, ks2, h2, SEED + sg * 3 + 9)
    kd2, kbp2 = kink_fit(ks2, Md2)
    kt2, _ = kink_fit(ks2, Mt2)
    Rc2 = kd2 / max(kt2, 1e-9)
    bi2 = list(ks2).index(kbp2) if kbp2 in list(ks2) else int(np.argmin(np.abs(ks2 - kbp2)))
    interior2 = 0 < bi2 < NK - 1
    split2 = split_anywhere(A, ks2, h2)
    f_h2 = v3_rule(Rc2, split2, interior2, kbp2, kf2, dk2)
    ck3[key] = dict(h1_fires=f_h1, h2_fires=f_h2, h2=dict(Rc=Rc2, split=bool(split2),
                    interior=bool(interior2), kbp=kbp2, kf=kf2))
    json.dump(ck3, open(CKPT3, "w"), default=float)
    print(f"g{sg}: v3 h1={int(f_h1)} | h2: Rc={Rc2:.2f} split={split2} int={interior2} "
          f"|kbp-kf|={abs(kbp2-kf2):.1f} vs 3dk={3*dk2:.1f} -> fires={int(f_h2)} [{time.time()-t0:.0f}s]", flush=True)

if all(f"g{sg}" in ck3 for sg in CYC):
    f1 = sum(1 for sg in CYC if ck3[f"g{sg}"]["h1_fires"])
    f2 = sum(1 for sg in CYC if ck3[f"g{sg}"]["h2_fires"])
    ps1 = f1 >= 4; ps1_kill = f1 <= 2
    ps2 = f2 <= 1; ps2_kill = f2 >= 2
    loo = all(sum(1 for j, sg in enumerate(CYC) if j != i and ck3[f"g{sg}"]["h1_fires"]) >= 3
              for i in range(5))
    ck3["verdicts"] = dict(f1=f1, f2=f2, PS1=bool(ps1), PS1_killed=bool(ps1_kill),
                           PS2=bool(ps2), PS2_killed=bool(ps2_kill), loo_ok=bool(loo))
    json.dump(ck3, open(CKPT3, "w"), default=float)
    print(f"\nP-S1: {f1}/5 -> {'ПОДТВЕРЖДЁН' if ps1 else ('УБИТ' if ps1_kill else 'не установлен')} (LOO={loo})")
    print(f"P-S2: h2 {f2}/5 -> {'ПОДТВЕРЖДЁН' if ps2 else ('УБИТ' if ps2_kill else 'не установлен')}")
    if any(ck3[f"g{sg}"]["h2_fires"] for sg in CYC):
        for sg in CYC:
            if ck3[f"g{sg}"]["h2_fires"]:
                print(f"P-S3: g{sg}-h2 сработал — механизм записать (окно над фолдом)")
print(f"[{time.time()-t0:.0f}s]")
