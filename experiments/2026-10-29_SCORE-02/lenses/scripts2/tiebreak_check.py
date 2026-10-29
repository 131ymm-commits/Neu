#!/usr/bin/env python3
"""LENSES-2: насколько огрубление без разрыва ничьих (single_c опыта) грубее согласия. На пилоте: AUC single_c опыта против AUC огрубления
с точным совпадением долей уровней (ничьи исходной шкалы разрываются случайно; среднее по 400 разрывам), и против огрубления до тех же
уровней «по рангу без ничьих» (rankdata method='ordinal' со случайным порядком внутри ничьей).
  python3 tiebreak_check.py <папка опыта>"""
import json
import os
import sys

import numpy as np

X = sys.argv[1]


def auc_pairs(c, o):
    p, n = c[o], c[~o]
    gt = (p[:, None] > n[None, :]).sum()
    eq = (p[:, None] == n[None, :]).sum()
    return float((gt + 0.5 * eq) / (len(p) * len(n)))


for st in ('pilot_opus', 'pilot_haiku'):
    E = json.load(open(os.path.join(X, 'evals', f'{st}.json'), encoding='utf-8'))['judgments']
    av = np.array([c for t in E for c, _ in E[t]['agree']])
    sv = np.array([c for t in E for c, _ in E[t]['single']])
    so = np.array([o for t in E for _, o in E[t]['single']], bool)
    ao = np.array([o for t in E for _, o in E[t]['agree']], bool)
    lv = np.unique(av)
    q = np.array([np.mean(av == v) for v in lv])
    N = len(sv)
    cnt = np.round(np.cumsum(q) * N).astype(int)
    rng = np.random.default_rng(5)
    aucs = []
    for _ in range(400):
        order = np.lexsort((rng.random(N), sv))   # по возрастанию sv, ничьи — случайно
        lev = np.empty(N)
        start = 0
        for j, e in enumerate(cnt):
            lev[order[start:e]] = lv[j]
            start = e
        aucs.append(auc_pairs(lev, so))
    print(f'{st}: AUC agree {auc_pairs(av, ao):.4f}; single {auc_pairs(sv, so):.4f}; single_c опыта — см. pilot_describe.json; '
          f'огрубление с точными долями (ничьи разорваны случайно) {np.mean(aucs):.4f} (SD по разрывам {np.std(aucs):.4f})')
D = json.load(open(os.path.join(X, 'pilot_describe.json'), encoding='utf-8'))
print('single_c опыта:', {st: round(D[st]['measures']['single_c']['auc2'], 4) for st in D})
