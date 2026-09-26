# EVO-04: анализ строго по PREREG-EVO-04.md (ИОИ, меньше — лучше)
import json, glob
import numpy as np
from scipy.stats import binom
R = {}
for f in glob.glob('runs/*.json'):
    d = json.load(open(f)); R[(d['task'], d['arm'], d['seed'])] = d
TASKS, S = ['T1', 'T2', 'T3', 'T4', 'T5', 'T6'], range(40, 60)
v = lambda k: 'подтверждено' if k >= 74 else ('опровергнуто' if k <= 60 else 'разницы нет')
def cmp(b, w):
    d = [R[(t, w, s)]['ioi'] - R[(t, b, s)]['ioi'] for t in TASKS for s in S]; k = sum(x > 0 for x in d)
    return dict(wins=k, ties=sum(x == 0 for x in d), verdict=v(k), median_gain=float(np.median(d)), sign_p=float(binom.sf(k - 1, len(d), .5)))
out = dict(PP1=cmp('PULSE10', 'LIFE2'), PP2=cmp('PULSE10', 'BASE'), PP3=cmp('PULSE3', 'PULSE10'),
           table={f'{t}/{a}': {k: float(np.median([R[(t, a, s)][k] for s in S])) for k in ('ioi', 'ignorance', 'deception', 'final_true', 'mean_n')}
                  for t in TASKS for a in ('BASE', 'LIFE2', 'PULSE10', 'PULSE3')})
json.dump(out, open('evo04_results.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: out[k] for k in ('PP1', 'PP2', 'PP3')}, ensure_ascii=False, indent=1))
for k, x in out['table'].items(): print(f"{k:12s} ИОИ {x['ioi']:.3f} незнание {x['ignorance']:.3f} самообман {x['deception']:.3f} итог {x['final_true']:.3f} n {x['mean_n']:.0f}")
