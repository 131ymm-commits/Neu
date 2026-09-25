# AUTO-05: анализ строго по PREREG-AUTO-05.md (метрика — excess как в AUTO-02)
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


SEEDS = list(range(70, 90))
rows = {s: {arm: excess(f'auto/{arm}_s{s}/p_02000.pkl') for arm in ('A0', 'AW', 'AR')} for s in SEEDS}
for s in SEEDS:
    print(s, {k: round(v, 5) for k, v in rows[s].items()})
dW = np.array([rows[s]['A0'] - rows[s]['AW'] for s in SEEDS])
dS = np.array([rows[s]['AR'] - rows[s]['AW'] for s in SEEDS])
dR = np.array([rows[s]['A0'] - rows[s]['AR'] for s in SEEDS])
v = lambda k: 'подтверждено' if k >= 16 else ('опровергнуто' if k <= 10 else 'разницы нет')
bs = lambda d: [float(np.percentile(np.median(np.random.default_rng(0).choice(d, (20000, len(d))), 1), q)) for q in (2.5, 97.5)]
out = dict(rows={str(k): w for k, w in rows.items()},
           P1=dict(n_positive=int((dW > 0).sum()), verdict=v(int((dW > 0).sum())), median=float(np.median(dW)), ci=bs(dW)),
           P2=dict(n_positive=int((dS > 0).sum()), verdict=v(int((dS > 0).sum())), median=float(np.median(dS)), ci=bs(dS),
                   sign_p=float(binom.sf(int((dS > 0).sum()) - 1, 20, 0.5))),
           P3=dict(AR_better_than_A0=int((dR > 0).sum()), median=float(np.median(dR)), ci=bs(dR)))
json.dump(out, open('auto05_results.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: w for k, w in out.items() if k != 'rows'}, ensure_ascii=False, indent=1))
