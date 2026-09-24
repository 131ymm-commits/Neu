"""ACH-01 пост-хок (не предрегистрировано): знак рождённого λ₂ и относительная форма косинуса c − c_min (семья №14/45)."""
import numpy as np, sys; sys.path.insert(0, '/home/claude')
src = open('/home/claude/ach01_run.py').read(); exec(src.split("parts = all_bipartitions(6); rng")[0])
parts = all_bipartitions(6); rng = np.random.default_rng(2026); neg = pos = 0; rel_c = []; rel_b = []; negonly = 0; cmin_pos = []
for _ in range(2000):
    P = random_chain(6, rng); pi = stationary(P); st = chain_stats(P, pi, parts); r = st['rows']
    born = r[:, 2] > 0.5; negb = born & (r[:, 3] < 0); posb = born & (r[:, 3] > 0); neg += int(negb.sum()); pos += int(posb.sum())
    if born.any() and not posb.any(): negonly += 1
    d = st['lmax'] - st['l2S']
    if posb.any() and d > 1e-12:
        cmin = float(np.sqrt(max(0.0, (st['rho'] - st['l2S']) / d))); cmin_pos.append(cmin); rel_c.extend(r[:, 0] - cmin); rel_b.extend(posb)
print(dict(neg_births=neg, pos_births=pos, chains_neg_only=negonly, auc_rel_pooled_pos=auc(np.array(rel_c), np.array(rel_b)), cmin_pos_median=float(np.median(cmin_pos)), cmin_pos_p90=float(np.percentile(cmin_pos, 90))))
