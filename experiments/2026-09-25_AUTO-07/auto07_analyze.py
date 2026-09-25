# AUTO-07: анализ строго по PREREG-AUTO-07.md
import json
import numpy as np
from scipy.stats import binom
SEEDS = list(range(130, 142))
ARMS = ['A0', 'N', 'S', 'P', 'C', 'F', 'B', 'M']
nll = {a: {s: [r for r in json.load(open(f'auto/{a}_s{s}/log.json')) if r['kind'] == 'test'][-1]['nll'] for s in SEEDS} for a in ARMS}
v = lambda k: 'подтверждено' if k >= 10 else ('опровергнуто' if k <= 7 else 'разницы нет')
def cmp(worse, better):
    d = np.array([nll[worse][s] - nll[better][s] for s in SEEDS]); k = int((d > 0).sum())
    return dict(n_better=k, verdict=v(k), median=float(np.median(d)), sign_p=float(binom.sf(k - 1, len(SEEDS), 0.5)))
out = dict(P1=cmp('A0', 'M'), P2=cmp('S', 'F'), P3=cmp('F', 'M'),
           P4={a: dict(median=float(np.median(list(nll[a].values()))), vs_A0=cmp('A0', a)) for a in ARMS if a != 'A0'},
           rows={s: {a: nll[a][s] for a in ARMS} for s in SEEDS})
out['P4_rank'] = sorted(ARMS, key=lambda a: np.median(list(nll[a].values())))
json.dump(out, open('auto07_results.json', 'w'), ensure_ascii=False, indent=1)
for s in SEEDS: print(s, {a: round(nll[a][s], 4) for a in ARMS})
print(json.dumps({k: w for k, w in out.items() if k != 'rows'}, ensure_ascii=False, indent=1))
