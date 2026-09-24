# AUTO-02: анализ строго по PREREG-AUTO-02.md (метрика — как excess в auto_analyze.py AUTO-01)
import json, pickle, os
import numpy as np
from eq01_common import *

rng = np.random.default_rng(999)
XA, _ = sample(2000, rng=rng)
xin = XA[:, :64]
POST, BEL, NLL = forward_filter(xin)
OPT = float(NLL.mean())


def excess(path):
    p = pickle.load(open(path, 'rb'))
    logp, _ = model_outputs(p, xin)
    return float(-np.take_along_axis(logp[:, :63], xin[:, 1:64, None], -1).mean()) - OPT


SEEDS = list(range(20, 30))
rows = {}
for s in SEEDS:
    rows[s] = {arm: {st: excess(f'auto/{arm}_s{s}/p_{st:05d}.pkl') for st in (1000, 2000)} for arm in ('A0', 'AW')}
    rows[s]['d1000'] = rows[s]['A0'][1000] - rows[s]['AW'][1000]
    rows[s]['d2000'] = rows[s]['A0'][2000] - rows[s]['AW'][2000]
    print(s, {k: (round(v, 5) if isinstance(v, float) else {a: round(b, 5) for a, b in v.items()}) for k, v in rows[s].items()})
d2 = np.array([rows[s]['d2000'] for s in SEEDS]); d1 = np.array([rows[s]['d1000'] for s in SEEDS])
n2, n1 = int((d2 >= 0.0005).sum()), int((d1 >= 0.0005).sum())
P1 = 'помогает' if n2 >= 7 else ('разницы нет' if n2 == 6 else 'не помогает (провал)')
bs = np.random.default_rng(0).choice(d2, (20000, len(d2))).mean(1)
from math import comb
pos = int((d2 > 0).sum()); sign_p = sum(comb(10, k) for k in range(pos, 11)) / 2 ** 10
out = dict(rows={str(k): v for k, v in rows.items()}, P1=dict(n_ge=n2, verdict=P1),
           P2=dict(n_ge=n1, passed=n1 <= 5),
           P3=dict(median_d2000=float(np.median(d2)), mean_d2000=float(d2.mean()),
                   ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                   n_positive=pos, sign_test_p_one_sided=sign_p),
           A0_excess2000_sd=float(np.std([rows[s]['A0'][2000] for s in SEEDS], ddof=1)))
json.dump(out, open('auto02_results.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in out.items() if k != 'rows'}, ensure_ascii=False, indent=1))
