#!/usr/bin/env python3
"""SCORE-02: меры источников уверенности и бутстреп по задачам — общие для описания пилота, мощности и анализа. Импорт ничего не пишет.
Суждения задачи — из evals/<этап>.json (score02.py metrics): {задача: {источник: [[уверенность, верно], …], cand: [[верных, сторон], …]}}.
Меры источника по набору задач (суждения всех задач вместе): AUC второго рода (через средние ранги, ничьи — ½), точность (доля верных
суждений), средняя уверенность, самообман = уверенность − точность, Брайер уверенности против верности; ИОИ = незнание (1 − точность)
+ самообман⁺ (max(0, самообман)) — experiments/truth.py, описательно.
single_c — один вызов, огрублённый до распределения уровней согласия (контроль равной грубости, PREREG §4, X1oc; LENSES-1, L3-1);
у него считается только AUC второго рода. Карта огрубления строится по тем суждениям, по которым считается мера: по всей выборке
этапа для оценки и заново на каждом пересэмпле бутстрепа (LENSES-2, П1-1: фиксированная карта занижала разброс при почти
единогласных вызовах; было «края в бутстрепе не пересчитываются», LENSES-1, L3-1 (а)).
Разности источников — на одном пересэмпле задач (бутстреп с возвращением; задача, взятая дважды, входит дважды)."""
import bisect
import json
import os
import zlib

import numpy as np
from scipy.stats import rankdata

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = ('single', 'mean', 'agree')
MEASURES = ('auc2', 'acc', 'conf', 'self_dec', 'brier', 'ign', 'dec_pos', 'ioi')
EPS = 1e-12   # края интервала по модулю меньше EPS считаются нулём: ошибка округления не даёт знака (сухой прогон, вызовы одинаковы)


def load(stage, evals_dir=None):
    E = json.load(open(os.path.join(evals_dir or os.path.join(HERE, 'evals'), f'{stage}.json'), encoding='utf-8'))
    return {t: {s: [(c, bool(o)) for c, o in v[s]] for s in SOURCES} for t, v in E['judgments'].items()}


def load_cand(stage, evals_dir=None):
    E = json.load(open(os.path.join(evals_dir or os.path.join(HERE, 'evals'), f'{stage}.json'), encoding='utf-8'))
    return {t: [tuple(x) for x in v.get('cand', [])] for t, v in E['judgments'].items()}


def coarse_map(J, tasks):
    """Огрубление одного вызова до распределения уровней согласия этапа. Уровни согласия v_1 < … < v_m и их доли q_j — по всем
    суждениям agree этапа; Q_j — накопленные доли. Значение x одного вызова получает уровень v_j с наименьшим j, при котором средний
    ранговый процентиль r(x) = (#{c < x} + #{c = x}/2) / N не больше Q_j (N — суждений single этапа): ничьи исходной шкалы не
    разрываются. Края считаются один раз по всей выборке этапа и в бутстрепе не пересчитываются.
    Возвращает ({x: уровень}, [(уровень, доля agree, доля single после огрубления), …])."""
    av = [c for t in tasks for c, _ in J[t]['agree']]
    sv = sorted(c for t in tasks for c, _ in J[t]['single'])
    if not av or not sv:
        return {}, []
    lv = sorted(set(av))
    q = [sum(1 for c in av if c == v) / len(av) for v in lv]
    Q = list(np.cumsum(q))
    Q[-1] = 1.0
    N = len(sv)
    cmap = {}
    for x in sorted(set(sv)):
        lo, hi = bisect.bisect_left(sv, x), bisect.bisect_right(sv, x)
        r = (lo + (hi - lo) / 2) / N
        j = next(k for k, Qk in enumerate(Q) if r <= Qk + EPS)
        cmap[x] = lv[j]
    got = [sum(1 for c in sv if cmap[c] == v) / N for v in lv]
    return cmap, list(zip(lv, q, got))


def coarse_vec(sc, ac):
    """То же огрубление, что coarse_map, по массивам: sc — уверенности single, ac — уверенности agree (с повторами пересэмпла).
    Возвращает огрублённые sc (значения — уровни ac); при пустом ac или sc — nan."""
    if len(ac) == 0 or len(sc) == 0:
        return np.full(len(sc), np.nan)
    lv, cnt = np.unique(ac, return_counts=True)
    Q = np.cumsum(cnt) / len(ac)
    Q[-1] = 1.0
    xs, xc = np.unique(sc, return_counts=True)
    r = (np.cumsum(xc) - xc + xc / 2) / len(sc)
    j = np.minimum(np.searchsorted(Q + EPS, r, side='left'), len(lv) - 1)
    return lv[j][np.searchsorted(xs, sc)]


def nonempty(J, tasks):
    """Число непустых уровней у agree и у single_c (по всей выборке этапа) — для оговорки «грубость не уравнена» (LENSES-2, П1-3)."""
    _, lv = coarse_map(J, tasks)
    return dict(agree=sum(1 for _, q, _ in lv if q > 0), single_c=sum(1 for _, _, g in lv if g > 0))


def arrays(J, tasks):
    """По задачам: {источник: (уверенности, верность)} — numpy-массивы (single_c строится в measures_arr)."""
    return [{s: (np.array([c for c, _ in J[t][s]], float), np.array([o for _, o in J[t][s]], bool)) for s in SOURCES} for t in tasks]


def auc2_np(conf, ok):
    npos, nneg = int(ok.sum()), int((~ok).sum())
    if npos == 0 or nneg == 0:
        return float('nan')
    r = rankdata(conf)
    return float((r[ok].sum() - npos * (npos + 1) / 2) / (npos * nneg))


def measures_arr(A, idx):
    out = {}
    cat = {s: (np.concatenate([A[i][s][0] for i in idx]) if idx else np.array([]),
               np.concatenate([A[i][s][1] for i in idx]) if idx else np.array([], bool)) for s in SOURCES}
    cat['single_c'] = (coarse_vec(cat['single'][0], cat['agree'][0]), cat['single'][1])
    for s in SOURCES + ('single_c',):
        c, o = cat[s]
        if len(c) == 0:
            out[s] = {m: float('nan') for m in MEASURES}
            out[s]['n'] = 0
            continue
        if s == 'single_c':
            out[s] = {m: float('nan') for m in MEASURES}
            out[s].update(auc2=float('nan') if np.isnan(c).any() else auc2_np(c, o), n=int(len(c)))
            continue
        conf, acc = float(c.mean()), float(o.mean())
        out[s] = dict(auc2=auc2_np(c, o), acc=acc, conf=conf, self_dec=conf - acc, brier=float(((c - o) ** 2).mean()),
                      ign=1 - acc, dec_pos=max(0.0, conf - acc), ioi=(1 - acc) + max(0.0, conf - acc), n=int(len(c)))
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


def ci95(xs):
    """95 % процентильный интервал; края по модулю меньше EPS — ноль."""
    lo, hi = pct(xs, 0.025), pct(xs, 0.975)
    return [0.0 if abs(x) < EPS else x for x in (lo, hi)]


def decomp_x2(J, cand, tasks):
    """Разложение X2 (LENSES-1, L3-2), описательно. По кандидатам с суждением agree (s ≠ ½): s — доля вызовов на верной стороне среди
    вызовов с p ≠ 0,5; T = среднее (1 − s)·1(s > ½). Приближение: X2 = самообман(agree) − самообман(single) ≈ (1 − уверенность single) − 2T.
    Возвращает T, приближение, факт X2, долю единогласных суждений agree (уверенность 1) и порог T, выше которого приближение даёт X2 < 0."""
    ss = [r / n for t in tasks for r, n in cand[t] if n and 2 * r != n]
    T = float(np.mean([(1 - s) * (s > 0.5) for s in ss])) if ss else float('nan')
    M = measures(J, tasks)
    un = [c for t in tasks for c, _ in J[t]['agree']]
    return dict(T=T, approx=(1 - M['single']['conf']) - 2 * T, x2=M['agree']['self_dec'] - M['single']['self_dec'],
                unanimous=float(np.mean([abs(c - 1) < EPS for c in un])) if un else float('nan'),
                T_break=(1 - M['single']['conf']) / 2, n_cand=len(ss))
