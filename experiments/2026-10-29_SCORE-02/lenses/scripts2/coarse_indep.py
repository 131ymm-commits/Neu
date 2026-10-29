#!/usr/bin/env python3
"""LENSES-2: огрубление одного вызова по тексту §2 черновика, своей реализацией (без score02_lib):
средний ранговый процентиль r = (средний ранг − ½)/N среди суждений single этапа; уровень — наименьший j с r ≤ Q_j (Q — накопленные доли
уровней agree этапа). AUC — попарно (верное > неверного, ничьи — ½), не через ранги. Сравнение с single_c из analysis/pilot json.
  python3 coarse_indep.py <папка опыта>"""
import json
import os
import sys

import numpy as np
from scipy.stats import rankdata

X = sys.argv[1]


def auc_pairs(c, o):
    c, o = np.asarray(c, float), np.asarray(o, bool)
    p, n = c[o], c[~o]
    if len(p) == 0 or len(n) == 0:
        return float('nan')
    gt = (p[:, None] > n[None, :]).sum()
    eq = (p[:, None] == n[None, :]).sum()
    return float((gt + 0.5 * eq) / (len(p) * len(n)))


def coarse(J):
    av = np.array([c for t in J for c, _ in J[t]['agree']])
    sv = np.array([c for t in J for c, _ in J[t]['single']])
    so = np.array([o for t in J for _, o in J[t]['single']], bool)
    lv = np.unique(av)
    Q = np.cumsum([np.mean(av == v) for v in lv])
    Q[-1] = 1.0
    r = (rankdata(sv) - 0.5) / len(sv)
    j = np.array([np.argmax(Q >= x - 1e-12) for x in r])
    sc = lv[j]
    return sc, so, lv, [float(np.mean(sc == v)) for v in lv]


def load(path):
    E = json.load(open(path, encoding='utf-8'))
    return {t: {s: [(c, bool(o)) for c, o in v[s]] for s in ('single', 'mean', 'agree')} for t, v in E['judgments'].items()}


D = json.load(open(os.path.join(X, 'pilot_describe.json'), encoding='utf-8'))
for st in ('pilot_opus', 'pilot_haiku'):
    J = load(os.path.join(X, 'evals', f'{st}.json'))
    sc, so, lv, sh = coarse(J)
    a = auc_pairs(sc, so)
    ref = D[st]['measures']['single_c']['auc2']
    refsh = [x['single_c_share'] for x in D[st]['describe']['levels']]
    print(f'{st}: AUC single_c своё {a:.12f}, в json {ref:.12f}; доли своё {np.round(sh, 4).tolist()}, в json {np.round(refsh, 4).tolist()}')
for br in ('A', 'N0', 'N2', 'E', 'C', 'D'):
    A = json.load(open(os.path.join(X, 'dry', f'analysis_{br}.json'), encoding='utf-8'))
    # evals ветки на диске нет (перезаписаны последней веткой); сверяю только ветку D, чьи evals лежат в dry/evals
    if br != 'D':
        continue
    for st in ('main_opus', 'rep_opus', 'main_haiku', 'rep_haiku'):
        J = load(os.path.join(X, 'dry', 'evals', f'{st}.json'))
        sc, so, lv, sh = coarse(J)
        print(f'D {st}: AUC single_c своё {auc_pairs(sc, so):.12f}, в analysis_D.json {A["measures"][st]["single_c"]["auc2"]:.12f}')
