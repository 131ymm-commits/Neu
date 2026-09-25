# AUTO-06: анализ строго по PREREG-AUTO-06.md
import json
import numpy as np
from scipy.stats import binom
SEEDS = list(range(110, 122))
ARMS = ['A0', 'N1', 'N1024', 'N4096', 'F1024', 'F4096']
nll = {a: {s: [r for r in json.load(open(f'auto/{a}_s{s}/log.json')) if r['kind'] == 'test'][-1]['nll'] for s in SEEDS} for a in ARMS}
v = lambda k: 'подтверждено' if k >= 10 else ('опровергнуто' if k <= 7 else 'разницы нет')
def cmp(worse, better):
    d = np.array([nll[worse][s] - nll[better][s] for s in SEEDS]); k = int((d > 0).sum())
    return dict(n_better=k, verdict=v(k), median=float(np.median(d)), sign_p=float(binom.sf(k - 1, len(SEEDS), 0.5)))
out = dict(P1=cmp('A0', 'N4096'), P2=cmp('N1', 'N4096'), P3=cmp('N4096', 'F4096'),
           P4={a: dict(median=float(np.median(list(nll[a].values()))), vs_A0=cmp('A0', a) if a != 'A0' else None) for a in ARMS},
           rows={s: {a: nll[a][s] for a in ARMS} for s in SEEDS})
json.dump(out, open('auto06_results.json', 'w'), ensure_ascii=False, indent=1)
for s in SEEDS: print(s, {a: round(nll[a][s], 4) for a in ARMS})
print(json.dumps({k: w for k, w in out.items() if k != 'rows'}, ensure_ascii=False, indent=1))
