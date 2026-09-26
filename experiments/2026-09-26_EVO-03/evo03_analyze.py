# EVO-03: анализ строго по PREREG-EVO-03.md (мера — ИОИ, меньше — лучше)
import json, glob
import numpy as np
from scipy.stats import binom, spearmanr
R = {}
for f in glob.glob('runs/*.json'):
    d = json.load(open(f)); R[(d['task'], d['arm'], d['seed'])] = d
S = range(20, 40)
v = lambda k: 'подтверждено' if k >= 40 else ('опровергнуто' if k <= 30 else 'разницы нет')
def cmp(b, w, tasks):
    d = [R[(t, w, s)]['ioi'] - R[(t, b, s)]['ioi'] for t in tasks for s in S]     # >0 — b лучше
    k = sum(x > 0 for x in d)
    return dict(wins=k, ties=sum(x == 0 for x in d), median_gain=float(np.median(d)), sign_p=float(binom.sf(k - 1, len(d), .5)))
A = ['T1', 'T2', 'T3']; ST = ['T2', 'T4', 'T5']; UN = ['T1', 'T3', 'T6']
out = {}
out['PA1'] = cmp('MIRROR_50', 'MIRROR_0', A); out['PA1']['verdict'] = v(out['PA1']['wins'])
out['PA2'] = cmp('MIRROR_100', 'MIRROR_0', A); out['PA2']['verdict'] = v(out['PA2']['wins'])
out['PB1'] = cmp('TWO', 'BASE', ST); out['PB1']['verdict'] = v(out['PB1']['wins'])
pb2 = cmp('TWO', 'BASE', UN); k = pb2['wins']
pb2['verdict'] = 'подтверждено' if k <= 30 else ('опровергнуто' if k >= 40 else 'разницы нет'); out['PB2'] = pb2
pc = cmp('LIFE2', 'BASE', A); pc_b = cmp('BASE', 'LIFE2', A)
pc['verdict'] = 'помогает' if pc['wins'] >= 40 else ('вредит' if pc_b['wins'] >= 40 else 'разницы нет'); pc['base_wins'] = pc_b['wins']; out['PC'] = pc
rho = [spearmanr([0, 25, 50, 100], [R[(t, f'MIRROR_{f}', s)]['ioi'] for f in (0, 25, 50, 100)]).statistic for t in A for s in S]
out['explore'] = dict(mirror_dose_rho_median=float(np.nanmedian(rho)),
                      table={f'{t}/{a}': {k2: float(np.median([R[(t, a, s)][k2] for s in S])) for k2 in ('ioi', 'ignorance', 'deception', 'final_true')}
                             for (t, a) in sorted({(t, a) for (t, a, s) in R})})
json.dump(out, open('evo03_results.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k2: out[k2] for k2 in out if k2 != 'explore'}, ensure_ascii=False, indent=1))
print('ρ(доля новизны, ИОИ), медиана:', round(out['explore']['mirror_dose_rho_median'], 3))
for k2, x in out['explore']['table'].items(): print(f"{k2:14s} ИОИ {x['ioi']:.3f}  незнание {x['ignorance']:.3f}  самообман {x['deception']:.3f}  итог {x['final_true']:.3f}")
