# EVO-02: анализ строго по PREREG-EVO-02.md
import json, glob
import numpy as np
from scipy.stats import binom
R = {}
for f in glob.glob('runs/*.json'):
    d = json.load(open(f)); R[(d['task'], d['arm'], d['seed'])] = d
TASKS, SEEDS, ARMS = ['T1', 'T2', 'T3'], range(20), ['BASE', 'HGT', 'LIFE', 'TWO', 'SPLIT']
auc = lambda d: float(np.mean([h['true'] for h in d['hist']]))
v = lambda k: 'подтверждено' if k >= 40 else ('опровергнуто' if k <= 30 else 'разницы нет')
def cmp(b, w):
    d = [auc(R[(t, b, s)]) - auc(R[(t, w, s)]) for t in TASKS for s in SEEDS]
    k = sum(x > 0 for x in d); ties = sum(x == 0 for x in d)
    return dict(wins=k, ties=ties, losses=len(d) - k - ties, verdict=v(k), median=float(np.median(d)), sign_p=float(binom.sf(k - 1, len(d), .5)))
out = dict(P1=cmp('HGT', 'BASE'), P2=cmp('TWO', 'SPLIT'), P3=cmp('TWO', 'BASE'), P4_LIFE_vs_BASE=cmp('LIFE', 'BASE'),
           table={a: {t: dict(auc=float(np.median([auc(R[(t, a, s)]) for s in SEEDS])), final_true=float(np.median([R[(t, a, s)]['final_true'] for s in SEEDS])),
                              final_claimed=float(np.median([R[(t, a, s)]['final_claimed'] for s in SEEDS])), n_end=float(np.median([R[(t, a, s)]['hist'][-1]['n'] for s in SEEDS])))
                      for t in TASKS} for a in ARMS})
json.dump(out, open('evo02_results.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: out[k] for k in out if k != 'table'}, ensure_ascii=False, indent=1))
for a in ARMS: print(a, {t: (round(x['auc'], 3), round(x['final_true'], 3), round(x['final_claimed'], 3), x['n_end']) for t, x in out['table'][a].items()})
