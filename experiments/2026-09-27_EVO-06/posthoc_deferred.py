# Пост-хок: отложенные гипотезы Г1–Г3 (DEFERRED_hypotheses.md), вскрыты один раз после основного прогона. Вердикта PREREG не меняют.
import json, glob, os, statistics as st
from scipy.stats import spearmanr
D = os.path.dirname(os.path.abspath(__file__)); R = {}
for f in glob.glob(f'{D}/runs/T*_s*.json'):
    d = json.load(open(f)); R[(d['task'], d['arm'], d['seed'])] = d
def W(d): return d['hist'][-30:]
out = {}
# Г1: D = mean(C−T | elite_age=0) − mean(C−T | elite_age≥1) в окне
g1 = {}
for arm in ('SAME32', 'SPLIT16+16', 'SAME16', 'SPLIT8+8'):
    per_task = {}
    for (t, a, s), d in R.items():
        if a != arm or t not in ('T3', 'T4', 'T5'): continue
        w = W(d); new = [h['claimed'] - h['true'] for h in w if h['elite_age'] == 0]; old = [h['claimed'] - h['true'] for h in w if h['elite_age'] >= 1]
        if new and old: per_task.setdefault(t, []).append(st.mean(new) - st.mean(old))
    g1[arm] = {t: dict(n=len(v), median=round(st.median(v), 4), share_pos=round(sum(x > 0 for x in v) / len(v), 2)) for t, v in per_task.items()}
    allv = [x for v in per_task.values() for x in v]; g1[arm]['all'] = dict(n=len(allv), median=round(st.median(allv), 4), share_pos=round(sum(x > 0 for x in allv) / len(allv), 2))
out['G1'] = g1
# Г2: FIXED32 плато заявки; Δ = true(150) − true(121); доля claimed=1 & true<0.9; elite_age(150) FIXED32 vs SAME32
g2 = {}
for t in ('T3', 'T4', 'T5'):
    plate = []; dl = []; c1 = 0; n = 0; age_w = 0; age_d = []
    for s in range(80, 100):
        f = R[(t, 'FIXED32', s)]; sm = R[(t, 'SAME32', s)]; w = W(f); n += 1
        if len({round(h['claimed'], 6) for h in w}) == 1:
            plate.append(s); dl.append(w[-1]['true'] - w[0]['true'])
        if w[-1]['claimed'] >= 0.999 and w[-1]['true'] < 0.9: c1 += 1
        af = f['hist'][-1]['elite_age']; asm = sm['hist'][-1]['elite_age']; age_w += af > asm; age_d.append(af - asm)
    g2[t] = dict(plateau_share=round(len(plate) / n, 2), delta_true_median=(round(st.median(dl), 4) if dl else None), claimed1_true_lt09=round(c1 / n, 2), age_fixed_gt_same32=f'{age_w}/{n}', age_diff_median=st.median(age_d))
out['G2'] = g2
# Г3: churn = доля поколений с elite_age=0 в окне; ρ Спирмена churn ~ abs_ct_late по сидам; churn SAME16 > SAME32
g3 = {}
for arm in ('SAME32', 'SAME16', 'SPLIT16+16', 'ORACLE'):
    for t in ('T4', 'T5'):
        ch = []; ab = []
        for s in range(80, 100):
            d = R[(t, arm, s)]; w = W(d); ch.append(st.mean(h['elite_age'] == 0 for h in w)); ab.append(d['abs_ct_late'])
        rho = spearmanr(ch, ab).correlation if len(set(ab)) > 1 and len(set(ch)) > 1 else None
        g3[f'{arm}/{t}'] = dict(churn_median=round(st.median(ch), 3), rho=(round(float(rho), 3) if rho is not None and rho == rho else None))
w16 = 0; n = 0
for t in ('T2', 'T3', 'T4', 'T5'):
    for s in range(80, 100):
        c16 = st.mean(h['elite_age'] == 0 for h in W(R[(t, 'SAME16', s)])); c32 = st.mean(h['elite_age'] == 0 for h in W(R[(t, 'SAME32', s)])); n += 1; w16 += c16 > c32
g3['churn_SAME16_gt_SAME32'] = f'{w16}/{n}'
out['G3'] = g3
json.dump(out, open(f'{D}/runs/posthoc_deferred.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
