#!/usr/bin/env python3
"""LENSES-2: мощность ожидания ветки N2 сухого прогона («X2 опровергнуто») — та же заглушка logit (a 0,3, c 0,3, s 1, p округлено до
0,001), разные зёрна; X2 = самообман(agree) − самообман(single) по суждениям score02.judgments, бутстреп задач B = 4000, 95 % интервал.
  SCORE02_COPY=<копия> python3 n2_power.py <n задач> <повторов>"""
import math
import os
import sys

import numpy as np

X = os.environ['SCORE02_COPY']
sys.path.insert(0, X)
import score02 as S  # noqa: E402

n, R = int(sys.argv[1]), int(sys.argv[2])
a, c, s = 0.3, 0.3, 1.0
sig = lambda x: 1 / (1 + math.exp(-x))
lab = {0, 1, 2, 3}
z = [1.0] * 4 + [-1.0] * 4
rng = np.random.default_rng(777)
res = []
for r in range(R):
    T = np.zeros((n, 2, 3))   # [single, agree] × [сумма уверенности, верных, суждений]
    for t in range(n):
        u = rng.standard_normal(8)
        rows = {k: [round(sig(a * z[i] + c * u[i] + s * rng.standard_normal()), 3) for i in range(8)] for k in range(5)}
        J = S.judgments(rows, lab, 5)
        for si, src in enumerate(('single', 'agree')):
            T[t, si] = [sum(x for x, _ in J[src]), sum(o for _, o in J[src]), len(J[src])]
    W = rng.multinomial(n, np.full(n, 1 / n), size=4000).astype(float)
    S_ = np.einsum('bn,nsk->bsk', W, T)
    sd = S_[:, :, 0] / S_[:, :, 2] - S_[:, :, 1] / S_[:, :, 2]
    x2 = sd[:, 1] - sd[:, 0]
    pt = (T[:, 1, 0].sum() / T[:, 1, 2].sum() - T[:, 1, 1].sum() / T[:, 1, 2].sum()) - (T[:, 0, 0].sum() / T[:, 0, 2].sum() - T[:, 0, 1].sum() / T[:, 0, 2].sum())
    lo, hi = np.quantile(x2, [0.025, 0.975])
    res.append((pt, hi < 0))
pts = np.array([p for p, _ in res])
print(f'N2, n = {n}: X2 в среднем {pts.mean():+.4f} (SD {pts.std(ddof=1):.4f}); доля «опровергнуто» {np.mean([h for _, h in res]):.3f} из {R}')
