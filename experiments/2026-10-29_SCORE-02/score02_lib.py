#!/usr/bin/env python3
"""SCORE-02: меры источников уверенности и бутстреп по задачам — общие для описания пилота, мощности и анализа. Импорт ничего не пишет.
Суждения задачи — из evals/<этап>.json (score02.py metrics): {задача: {источник: [[уверенность, верно], …]}}.
Меры источника по набору задач (суждения всех задач вместе): AUC второго рода, точность (доля верных суждений), средняя уверенность,
самообман = уверенность − точность, Брайер уверенности против верности. Разности источников — на одном пересэмпле задач."""
import bisect
import json
import os
import random
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = ('single', 'mean', 'agree')
MEASURES = ('auc2', 'acc', 'conf', 'self_dec', 'brier')


def load(stage):
    E = json.load(open(os.path.join(HERE, 'evals', f'{stage}.json'), encoding='utf-8'))
    return {t: {s: [(c, bool(o)) for c, o in v[s]] for s in SOURCES} for t, v in E['judgments'].items()}


def auc2(js):
    pos = [c for c, o in js if o]
    neg = sorted(c for c, o in js if not o)
    if not pos or not neg:
        return float('nan')
    tot = 0.0
    for c in pos:
        lo, hi = bisect.bisect_left(neg, c), bisect.bisect_right(neg, c)
        tot += lo + 0.5 * (hi - lo)
    return tot / (len(pos) * len(neg))


def measures(J, tasks):
    out = {}
    for s in SOURCES:
        js = [j for t in tasks for j in J[t][s]]
        if not js:
            out[s] = {m: float('nan') for m in MEASURES}
            continue
        conf = sum(c for c, _ in js) / len(js)
        acc = sum(1 for _, o in js if o) / len(js)
        out[s] = dict(auc2=auc2(js), acc=acc, conf=conf, self_dec=conf - acc, brier=sum((c - o) ** 2 for c, o in js) / len(js), n=len(js))
    return out


def contrast(M, spec):
    """spec = (мера, источник A, источник B) → M[A][мера] − M[B][мера]."""
    m, a, b = spec
    return M[a][m] - M[b][m]


def bootstrap(J, tasks, specs, B=10000, name='', n_out=None):
    """Бутстреп задач (с возвращением; размер выборки — n_out или число задач); для каждого spec — список значений контраста."""
    rng = random.Random(zlib.crc32(f'SCORE-02|{name}'.encode()))
    n = n_out or len(tasks)
    res = {sp: [] for sp in specs}
    for _ in range(B):
        smp = [rng.choice(tasks) for _ in range(n)]
        # задачи с повтором — как отдельные копии: суждения повторяются
        M = measures({**{f'{t}#{i}': J[t] for i, t in enumerate(smp)}}, [f'{t}#{i}' for i, t in enumerate(smp)])
        for sp in specs:
            res[sp].append(contrast(M, sp))
    return res


def pct(xs, q):
    ys = sorted(x for x in xs if x == x)
    if not ys:
        return float('nan')
    k = q * (len(ys) - 1)
    lo, hi = int(k), min(int(k) + 1, len(ys) - 1)
    return ys[lo] + (ys[hi] - ys[lo]) * (k - lo)
