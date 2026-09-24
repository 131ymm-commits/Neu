"""OL-001b — where the adenine handle sits. Per PREREG."""
import json, numpy as np
src = open("/home/claude/ol001_run.py").read().split('rng = np.random.default_rng(20260825)')[0]
exec(src)  # reuse frozen rules/data: parse_sbml, base, is_tag, is_ade, INORG, CUR, MODELS

rng = np.random.default_rng(20260826)
out = {}
pool_deg, pool_ade = [], []
for org in MODELS:
    names, deg = parse_sbml(MODELS[org])
    cur_bases = []
    for c in CUR[org]:
        b = base(c)
        if b not in cur_bases: cur_bases.append(b)
    skel_org = [b for b in names if b not in INORG and b not in cur_bases]
    tagged_skel = [b for b in skel_org if is_tag(b, names.get(b))]
    ade_flags = [is_ade(b, names.get(b)) for b in tagged_skel]
    f_ade_skel = float(np.mean(ade_flags))
    degs = [deg[b] for b in tagged_skel]
    pool_deg += [np.log2(max(d, 1)) for d in degs]
    pool_ade += [int(a) for a in ade_flags]
    out[org] = dict(n_tagged_skel=len(tagged_skel), f_ade_skel=f_ade_skel,
                    examples_ade=[b for b, a in zip(tagged_skel, ade_flags) if a][:8],
                    examples_non=[b for b, a in zip(tagged_skel, ade_flags) if not a][:8])
    print(f"{org}: меченый каркас n={len(tagged_skel)}  аденин-доля={f_ade_skel:.3f}  "
          f"(валютная была 1.00)", flush=True)
    print(f"   не-аденин примеры: {out[org]['examples_non']}")

from scipy.stats import spearmanr
rho, p_asym = spearmanr(pool_deg, pool_ade)
nperm = 10000
perm_r = np.empty(nperm)
pa = np.array(pool_ade); pd_ = np.array(pool_deg)
for i in range(nperm):
    perm_r[i] = spearmanr(pd_, rng.permutation(pa))[0]
p_perm = float(np.mean(perm_r >= rho))
lt06 = sum(1 for o in out.values() if o["f_ade_skel"] < 0.6)
ge08 = sum(1 for o in out.values() if o["f_ade_skel"] >= 0.8)
below_cur = sum(1 for o in out.values() if o["f_ade_skel"] < 1.0)
print(f"\nP-A1: <0.6 в {lt06}/4; всюду ниже валютной(1.00): {below_cur}/4; убийца >=0.8 в {ge08}/4"
      f" -> {'ПОДТВЕРЖДЁН' if (lt06>=3 and below_cur==4) else ('УБИТ' if ge08>=3 else 'не установлен')}")
print(f"P-A2: Spearman rho(log2 deg, аденин | меченый каркас, пул n={len(pool_ade)}) = {rho:.3f}, "
      f"p_perm={p_perm:.4f} -> {'ПОДТВЕРЖДЁН' if (rho>0 and p_perm<0.05) else ('УБИТ' if rho<=0 else 'не установлен')}")
for skip in out:
    idx = [i for i, org in enumerate([o for o in MODELS for _ in range(out[o]['n_tagged_skel'])]) ]
# LOO by recompute
offs = {}
i0 = 0
for org in MODELS:
    n = out[org]["n_tagged_skel"]; offs[org] = (i0, i0 + n); i0 += n
for org in MODELS:
    a, b_ = offs[org]
    m = np.ones(len(pool_ade), bool); m[a:b_] = False
    r_, _ = spearmanr(pd_[m], pa[m])
    print(f"  LOO без {org}: rho={r_:.3f}")
out["pooled"] = dict(rho=float(rho), p_perm=p_perm, n=len(pool_ade))
json.dump(out, open("/home/claude/ol001b_results.json", "w"))
print("-> ol001b_results.json")
