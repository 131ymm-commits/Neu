"""DET-016d — v4 continuity leg on extended window. MF-only recompute from frozen ckpts."""
import json
import numpy as np

exec(open("/home/claude/det016b_run.py").read().split("ck = json.load")[0])

ckb = json.load(open("/home/claude/det016b_ckpt.json"))
ck3 = json.load(open("/home/claude/det016c_ckpt.json"))
FL = ckb["floors"]

def split_ext(A, kf, hfun):
    for k in np.linspace(0.25 * kf, 2.5 * kf, 8):
        lo = mf_relax(A, k, hfun, np.full(M, EPS), 60000).sum()
        hi = mf_relax(A, k, hfun, np.full(M, 12.0), 60000).sum()
        if abs(hi - lo) > 0.5: return True
    return False

out = {}
f1 = f2 = 0
for sg in CYC:
    edges = edges_seq(M, sg)
    A = adj_at(edges, M, k_cycle(edges, M))
    e2 = ckb[f"g{sg}"]
    e3 = ck3[f"g{sg}"]
    ks = np.array(e2["ks"]); dk = ks[1] - ks[0]
    # h1 v4
    s1 = split_ext(A, e2["kf"], h1)
    v4_h1 = bool(e2["Rc"] >= FL["floor_c"] and not s1 and e2["interior"]
                 and abs(e2["kbp"] - e2["kf"]) <= 3 * dk + 1e-9)
    # h2 v4
    kf2 = e3["h2"]["kf"]
    dk2 = 1.1 * kf2 / 14.0
    s2 = split_ext(A, kf2, h2)
    v4_h2 = bool(e3["h2"]["Rc"] >= FL["floor_c"] and not s2 and e3["h2"]["interior"]
                 and abs(e3["h2"]["kbp"] - kf2) <= 3 * dk2 + 1e-9)
    out[sg] = dict(h1=v4_h1, h1_split_ext=bool(s1), h2=v4_h2, h2_split_ext=bool(s2))
    f1 += v4_h1; f2 += v4_h2
    print(f"g{sg}: v4 h1={int(v4_h1)} (ext_split={s1}) | h2={int(v4_h2)} (ext_split={s2})", flush=True)

pt1 = f2 == 0; pt1_kill = f2 >= 1
pt2 = f1 >= 4; pt2_kill = f1 <= 2
out["verdicts"] = dict(f1=f1, f2=f2, PT1=bool(pt1), PT1_killed=bool(pt1_kill),
                       PT2=bool(pt2), PT2_killed=bool(pt2_kill))
json.dump(out, open("/home/claude/det016d_results.json", "w"), default=float)
print(f"\nP-T1 (ложные h2 = 0): {'ПОДТВЕРЖДЁН' if pt1 else 'УБИТ'} ({f2}/5)")
print(f"P-T2 (h1 не тронуты, 4/5): {'ПОДТВЕРЖДЁН' if pt2 else ('УБИТ' if pt2_kill else 'не установлен')} ({f1}/5)")
