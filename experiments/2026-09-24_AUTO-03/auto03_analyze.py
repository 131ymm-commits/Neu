# AUTO-03: анализ строго по PREREG-AUTO-03.md (метрика — excess как в AUTO-02)
import json, pickle, os, itertools
import numpy as np
from math import comb
from scipy.stats import binom
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


SEEDS = list(range(30, 50))
rows = {}
for s in SEEDS:
    rows[s] = {arm: {st: excess(f'auto/{arm}_s{s}/p_{st:05d}.pkl') for st in (1000, 2000)} for arm in ('A0', 'AW')}
    rows[s]['d1000'] = rows[s]['A0'][1000] - rows[s]['AW'][1000]
    rows[s]['d2000'] = rows[s]['A0'][2000] - rows[s]['AW'][2000]
    print(s, round(rows[s]['A0'][2000], 5), round(rows[s]['AW'][2000], 5), 'Δ2000', round(rows[s]['d2000'], 5))
d2 = np.array([rows[s]['d2000'] for s in SEEDS]); d1 = np.array([rows[s]['d1000'] for s in SEEDS])

pos = int((d2 > 0).sum())
P1 = 'подтверждено' if pos >= 16 else ('опровергнуто' if pos <= 10 else 'разницы нет')
n2 = int((d2 >= 0.0005).sum())
P2 = 'подтверждено' if n2 >= 14 else ('опровергнуто' if n2 <= 9 else 'разницы нет')

# калибровка заново: разность excess(A0) двух разных сидов, все упорядоченные пары
a0 = np.array([rows[s]['A0'][2000] for s in SEEDS])
nd = np.array([a0[i] - a0[j] for i, j in itertools.permutations(range(len(a0)), 2)])
p0 = float((nd >= 0.0005).mean())
fl_P2 = float(binom.sf(13, 20, p0))
if P2 == 'подтверждено' and fl_P2 > 0.05:
    P2 = 'подтверждено по кромке'

bs = np.random.default_rng(0).choice(d2, (20000, len(d2)))
out = dict(rows={str(k): v for k, v in rows.items()},
           P1=dict(n_positive=pos, verdict=P1, false_level=float(binom.sf(15, 20, 0.5)),
                   sign_p_one_sided=float(binom.sf(pos - 1, 20, 0.5))),
           P2=dict(n_ge=n2, verdict=P2, p0_auto02=0.378, false_level_auto02=float(binom.sf(13, 20, 0.378)),
                   p0_recalibrated=p0, false_level_recalibrated=fl_P2),
           P3=dict(median=float(np.median(d2)), mean=float(d2.mean()),
                   ci95_mean=[float(np.percentile(bs.mean(1), 2.5)), float(np.percentile(bs.mean(1), 97.5))],
                   ci95_median=[float(np.percentile(np.median(bs, 1), 2.5)), float(np.percentile(np.median(bs, 1), 97.5))],
                   d1000_positive=int((d1 > 0).sum()), d1000_median=float(np.median(d1)),
                   A0_excess2000_median=float(np.median(a0)), A0_excess2000_sd=float(np.std(a0, ddof=1))))
prev = json.load(open('../2026-09-24_AUTO-02/auto02_results.json'))
d_prev = np.array([v['d2000'] for v in prev['rows'].values()])
d_all = np.concatenate([d_prev, d2])
out['P4'] = dict(n=len(d_all), positive=int((d_all > 0).sum()), ge_0005=int((d_all >= 0.0005).sum()), median=float(np.median(d_all)))
json.dump(out, open('auto03_results.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in out.items() if k != 'rows'}, ensure_ascii=False, indent=1))
