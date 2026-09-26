# EVO-01: анализ строго по PREREG-EVO-01.md
import json, glob
import numpy as np
from scipy.stats import binom
R = {}
for f in glob.glob('runs/*.json'):
    d = json.load(open(f)); R[(d['task'], d['arm'], d['seed'])] = d
TASKS, SEEDS = ['T1', 'T2', 'T3'], range(20)
ARMS = ['FIXED16', 'RANDOM16', 'RANDOM64', 'COEVO16', 'MIRROR16', 'ORACLE']
v = lambda k: 'подтверждено' if k >= 40 else ('опровергнуто' if k <= 30 else 'разницы нет')
def cmp(better, worse):
    d = [R[(t, better, s)]['final_true'] - R[(t, worse, s)]['final_true'] for t in TASKS for s in SEEDS]
    k = sum(x > 0 for x in d); ties = sum(x == 0 for x in d)
    return dict(wins=k, ties=ties, losses=len(d) - k - ties, verdict=v(k), median=float(np.median(d)), sign_p=float(binom.sf(k - 1, len(d), .5)))
out = dict(P1=cmp('RANDOM16', 'FIXED16'), P2=cmp('COEVO16', 'RANDOM64'), P3=cmp('MIRROR16', 'RANDOM16'),
           P4={a: {t: dict(true=float(np.median([R[(t, a, s)]['final_true'] for s in SEEDS])),
                           claimed=float(np.median([R[(t, a, s)]['final_claimed'] for s in SEEDS])),
                           labels=int(np.median([R[(t, a, s)]['labels'] for s in SEEDS]))) for t in TASKS} for a in ARMS})
json.dump(out, open('evo01_results.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: out[k] for k in ('P1', 'P2', 'P3')}, ensure_ascii=False, indent=1))
for a in ARMS: print(a, {t: (round(x['true'], 3), round(x['claimed'], 3), x['labels']) for t, x in out['P4'][a].items()})
