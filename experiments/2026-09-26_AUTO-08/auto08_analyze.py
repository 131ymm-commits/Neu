# AUTO-08: анализ строго по PREREG-AUTO-08.md
import json
import numpy as np
from scipy.stats import binom
SEEDS = list(range(150, 162)); ARMS = ['A0', 'F256', 'F1024', 'S1024']
nll = {a: {s: json.load(open(f'auto/{a}_s{s}.json'))[-1]['test'] for s in SEEDS} for a in ARMS}
v = lambda k: 'подтверждено' if k >= 10 else ('опровергнуто' if k <= 7 else 'разницы нет')
def cmp(w, b):
    d = np.array([nll[w][s] - nll[b][s] for s in SEEDS]); k = int((d > 0).sum())
    return dict(n_better=k, verdict=v(k), median=float(np.median(d)), sign_p=float(binom.sf(k - 1, 12, 0.5)))
out = dict(P1=cmp('A0', 'F1024'), P2=cmp('F256', 'F1024'), P3=cmp('S1024', 'F1024'),
           explore={a: dict(median=float(np.median(list(nll[a].values()))), vs_A0=cmp('A0', a)) for a in ARMS if a != 'A0'},
           A0_median=float(np.median(list(nll['A0'].values()))), rows={s: {a: nll[a][s] for a in ARMS} for s in SEEDS})
json.dump(out, open('auto08_results.json', 'w'), ensure_ascii=False, indent=1)
for s in SEEDS: print(s, {a: round(nll[a][s], 4) for a in ARMS})
print(json.dumps({k: w for k, w in out.items() if k != 'rows'}, ensure_ascii=False, indent=1))
