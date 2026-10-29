#!/usr/bin/env python3
"""SCORE-02: меры источников уверенности и бутстреп по задачам — общие для описания пилота, мощности и анализа. Импорт ничего не пишет.
Суждения задачи — из evals/<этап>.json (score02.py metrics): {задача: {источник: [[уверенность, верно], …]}}.
Меры источника по набору задач (суждения всех задач вместе): AUC второго рода (через средние ранги, ничьи — ½), точность (доля верных
суждений), средняя уверенность, самообман = уверенность − точность, Брайер уверенности против верности.
Разности источников — на одном пересэмпле задач (бутстреп с возвращением; задача, взятая дважды, входит дважды)."""
import json
import os
import zlib

import numpy as np
from scipy.stats import rankdata

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = ('single', 'mean', 'agree')
MEASURES = ('auc2', 'acc', 'conf', 'self_dec', 'brier')


def load(stage, evals_dir=None):
    E = json.load(open(os.path.join(evals_dir or os.path.join(HERE, 'evals'), f'{stage}.json'), encoding='utf-8'))
    return {t: {s: [(c, bool(o)) for c, o in v[s]] for s in SOURCES} for t, v in E['judgments'].items()}


def arrays(J, tasks):
    """По задачам: {источник: (уверенности, верность)} — numpy-массивы."""
    return [{s: (np.array([c for c, _ in J[t][s]], float), np.array([o for _, o in J[t][s]], bool)) for s in SOURCES} for t in tasks]


def auc2_np(conf, ok):
    npos, nneg = int(ok.sum()), int((~ok).sum())
    if npos == 0 or nneg == 0:
        return float('nan')
    r = rankdata(conf)
    return float((r[ok].sum() - npos * (npos + 1) / 2) / (npos * nneg))


def measures_arr(A, idx):
    out = {}
    for s in SOURCES:
        c = np.concatenate([A[i][s][0] for i in idx]) if idx else np.array([])
        o = np.concatenate([A[i][s][1] for i in idx]) if idx else np.array([], bool)
        if len(c) == 0:
            out[s] = {m: float('nan') for m in MEASURES}
            out[s]['n'] = 0
            continue
        conf, acc = float(c.mean()), float(o.mean())
        out[s] = dict(auc2=auc2_np(c, o), acc=acc, conf=conf, self_dec=conf - acc, brier=float(((c - o) ** 2).mean()), n=int(len(c)))
    return out


def measures(J, tasks):
    return measures_arr(arrays(J, tasks), list(range(len(tasks))))


def contrast(M, spec):
    """spec = (мера, источник A, источник B) → M[A][мера] − M[B][мера]."""
    m, a, b = spec
    return M[a][m] - M[b][m]


def bootstrap(J, tasks, specs, B=10000, name='', n_out=None):
    """Бутстреп задач: для каждого spec — список значений контраста на B пересэмплах (зерно — crc32 имени)."""
    A = arrays(J, tasks)
    rng = np.random.default_rng(zlib.crc32(f'SCORE-02|{name}'.encode()))
    n = n_out or len(tasks)
    res = {sp: [] for sp in specs}
    for _ in range(B):
        idx = list(rng.integers(0, len(tasks), n))
        M = measures_arr(A, idx)
        for sp in specs:
            res[sp].append(contrast(M, sp))
    return res


def pct(xs, q):
    ys = np.array([x for x in xs if x == x], float)
    return float(np.quantile(ys, q)) if len(ys) else float('nan')
