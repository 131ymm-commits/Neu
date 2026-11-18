#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-04 «СОВПАДЕНИЕ-СМЕЩЕНИЙ» — меры и нули (HYPOTHESIS.md, коммит 7aed3606: мера закреплена до разбора данных OCDIV-03).

Ядро (этот файл, часть 1):
- узор переносов κ(a, b) и страта c1 (в обоих семействах внутри области κ различает только перенос из единиц — проверено перебором);
- N3c — `ocdiv3.permute_wrong` со стратами c1: верные ответы и «без числа» на месте, неверные числовые смещения головы
  переставляются между её задачами с неверным ответом внутри страты;
- Δ3c = F − F₀(N3c); K — совпадение смещения при совместной ошибке пары голов минус то же при N3c;
- виды смещений (по слагаемым и коду, правда в отбор не входит).
Счёт по смещениям d = ответ − правда (`ocdiv2.dmat`), ложное большинство — `ocdiv2.false_major`: те же функции, что в OCDIV-02 и OCDIV-03."""
import itertools
import os
import sys

import numpy as np
from scipy.stats import t as student_t

X_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X_DIR))
EXP = os.path.join(ROOT, 'experiments')
sys.path.insert(0, os.path.join(EXP, '2026-11-17_OCDIV-03'))
import ocdiv3 as O3  # noqa: E402   OCDIV-03: permute_wrong, mean_entry; через него — ocdiv2 (W), P, S, V
W, P, S, V = O3.W, O3.P, O3.S, O3.V
NC = W.NONE_CODE
CROWD = W.CROWD
LEVEL, DESCR_LEVEL = P.LEVEL, P.DESCR_LEVEL


# ───────────── строение задачи (только слагаемые)
def kappa(a, b):
    """Узор переносов: перенос из каждого разряда a при столбиковом сложении a + b (младший разряд первым)."""
    out, c = [], 0
    for k in range(len(str(a))):
        s = (a // 10 ** k) % 10 + (b // 10 ** k) % 10 + c
        c = 1 if s >= 10 else 0
        out.append(c)
    return tuple(out)


def c1_of(a, b):
    """Перенос из разряда единиц."""
    return int(a % 10 + b % 10 >= 10)


def strata_c1(probs, cols):
    return np.array([c1_of(probs[j]['a'], probs[j]['b']) for j in cols], dtype=np.int64)


def cells_c1u(probs, cols):
    """Описательно: клетки «c1 × u», u — цифра десятков суммы (как ocdiv3.cell_of)."""
    return np.array([O3.cell_of(probs[j]['a'], probs[j]['b']) for j in cols], dtype=np.int64)


# ───────────── нуль N3c и Δ3c
def permute_wrong(D, rng, strata):
    """N3c: тот же код, что N3 OCDIV-03 (`ocdiv3.permute_wrong`), страты — c1."""
    return O3.permute_wrong(D, rng, strata)


def f0_n3c(D, strata, rng, K):
    return float(np.mean([W.false_major(permute_wrong(D, rng, strata)).mean() for _ in range(K)]))


def d3c_point(D, strata, rng, K):
    F = float(W.false_major(D).mean())
    F0 = f0_n3c(D, strata, rng, K)
    return F, F0, F - F0


def d3c_stream(D, strata, seed, seed_boot, B, K_point, K_boot):
    """Δ3c: точка (K_point перестановок) и повторы бутстрепа строк задач своим потоком (страта идёт со строкой), как ocdiv3.t4_stream."""
    n = D.shape[0]
    F, F0, dF = d3c_point(D, strata, np.random.default_rng(seed), K_point)
    gb = np.random.default_rng(seed_boot)
    bt = []
    for _ in range(B):
        rows = gb.integers(0, n, n)
        bt.append(d3c_point(D[rows], strata[rows], gb, K_boot)[2])
    bt = np.array(bt)
    return dict(F=F, F0=F0, point=dF, sd=float(np.std(bt, ddof=1)) if B > 1 else float('nan'), n=int(n)), bt


# ───────────── K: совпадение смещения при совместной ошибке
def wrong_num(D):
    return (D != 0) & (D < NC)


def pair_counts(D):
    """По парам голов (i < j): число задач, где обе дали неверное числовое смещение, и где оно одно и то же."""
    wr = wrong_num(D)
    out = []
    for i, j in itertools.combinations(range(D.shape[1]), 2):
        co = wr[:, i] & wr[:, j]
        out.append((int(co.sum()), int((co & (D[:, i] == D[:, j])).sum())))
    return out


def k_raw(D):
    """Среднее по парам с хотя бы одной совместной ошибкой доли совпавших смещений среди совместных ошибок."""
    v = [s / c for c, s in pair_counts(D) if c > 0]
    return float(np.mean(v)) if v else float('nan')


def k_point(D, strata, rng, K):
    """K = k_raw − среднее k_raw при N3c. Под N3c множества совместных ошибок пар не меняются (тест кода)."""
    k0 = float(np.mean([k_raw(permute_wrong(D, rng, strata)) for _ in range(K)]))
    kr = k_raw(D)
    return kr, k0, kr - k0


def k_stream(D, strata, seed, seed_boot, B, K_point, K_boot):
    n = D.shape[0]
    kr, k0, dk = k_point(D, strata, np.random.default_rng(seed), K_point)
    gb = np.random.default_rng(seed_boot)
    bt = []
    for _ in range(B):
        rows = gb.integers(0, n, n)
        bt.append(k_point(D[rows], strata[rows], gb, K_boot)[2])
    bt = np.array(bt)
    return dict(K_raw=kr, K0=k0, point=dk, sd=float(np.std(bt, ddof=1)) if B > 1 else float('nan'), n=int(n)), bt


# ───────────── виды смещений (по слагаемым и коду)
def offset_kind(d):
    d = int(d)
    if d == 0:
        return 'верно'
    if d >= NC:
        return 'без числа'
    for k in range(1, 7):
        p = 10 ** k
        if d == -p:
            return f'−10^{k}'
        if d == p:
            return f'+10^{k}'
        if d == 9 * p:
            return f'+9·10^{k}'
        if d == -9 * p:
            return f'−9·10^{k}'
    if abs(d) < 10:
        return 'малое (|d| < 10)'
    return 'прочее'


def kinds_of_head(col):
    """Доли видов среди неверных числовых смещений одной головы и пять самых частых смещений."""
    w = [int(x) for x in col if x != 0 and x < NC]
    if not w:
        return dict(n_wrong=0, kinds={}, top=[])
    ks, vals = {}, {}
    for d in w:
        ks[offset_kind(d)] = ks.get(offset_kind(d), 0) + 1
        vals[d] = vals.get(d, 0) + 1
    top = sorted(vals.items(), key=lambda x: (-x[1], x[0]))[:5]
    return dict(n_wrong=len(w), kinds={k: v / len(w) for k, v in sorted(ks.items(), key=lambda x: -x[1])},
                top=[dict(d=d, share=c / len(w)) for d, c in top])


def same_pairs_by_kind(D):
    """Совпавшие при совместной ошибке смещения пар — доли по видам."""
    wr = wrong_num(D)
    ks, tot = {}, 0
    for i, j in itertools.combinations(range(D.shape[1]), 2):
        m = wr[:, i] & wr[:, j] & (D[:, i] == D[:, j])
        for d in D[m, i]:
            ks[offset_kind(d)] = ks.get(offset_kind(d), 0) + 1
            tot += 1
    return dict(n=tot, kinds={k: v / tot for k, v in sorted(ks.items(), key=lambda x: -x[1])} if tot else {})


# ───────────── сводка по средам: среднее (M4) и t по средам
def t_envs(points):
    """Односторонний t по средам (среды как выборка, df = n − 1) и квантиль Стьюдента при уровне PREREG на сторону."""
    x = np.array(list(points.values()), float)
    n = len(x)
    if n < 2 or np.std(x, ddof=1) == 0:
        return dict(t=float('nan'), df=n - 1, crit=float('nan'))
    return dict(t=float(x.mean() / (np.std(x, ddof=1) / np.sqrt(n))), df=n - 1, crit=float(student_t.ppf(1 - LEVEL, n - 1)))


def mean_entry(points, boots, names, level):
    """M4 среднего сред — тот же код, что OCDIV-03 (`ocdiv3.mean_entry`)."""
    return O3.mean_entry(points, boots, names, level)
