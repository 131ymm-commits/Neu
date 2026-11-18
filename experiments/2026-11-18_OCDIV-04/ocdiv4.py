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
sys.path.insert(0, X_DIR)
import ocdiv4_extract as X4  # noqa: E402   среды OCDIV-04 (pilot3, test3)
W, P, S, V = O3.W, O3.P, O3.S, O3.V
NC = W.NONE_CODE
CROWD = W.CROWD
LEVEL, DESCR_LEVEL = P.LEVEL, P.DESCR_LEVEL


# ───────────── сборка ответов фаз OCDIV-04
def merge4(out_dir, phase, family, job_dirs):
    """Сборка тем же кодом, что OCDIV-02 (`ocdiv2.merge`: сверка номеров задач, ключей (a, b), sha256 подсказки и ревизий — СТОП при
    расхождении), но со средами фаз OCDIV-04: на время вызова `ocdiv2.D2.envs_ocdiv2` отдаёт среды `ocdiv4_extract.envs_ocdiv4`."""
    assert phase in X4.PHASES4, phase
    orig = W.D2.envs_ocdiv2
    W.D2.envs_ocdiv2 = lambda ph, fams=None: X4.envs_ocdiv4(ph, fams)
    try:
        return W.merge(out_dir, phase, family, job_dirs)
    finally:
        W.D2.envs_ocdiv2 = orig


def off4(meta):
    """Смещение зёрен среды OCDIV-04: 100·(номер семейства) + номер X в семействе (см. X4.FAMILIES4)."""
    fam = meta['family']
    o = 100 * list(X4.FAMILIES4).index(fam) + list(X4.FAMILIES4[fam]).index(int(meta['X']))
    assert 0 <= o < 200, o                                        # совет 72: смещение зёрен — в пределах двух семейств
    return o


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


# ═══════════════ часть 2: среды, вброс, мощность, правила (HYPOTHESIS §4–§7а)
import concurrent.futures as cf  # noqa: E402
import json  # noqa: E402
import platform  # noqa: E402
import time  # noqa: E402

import scipy  # noqa: E402
from scipy.stats import chi2, norm  # noqa: E402

FAMS = ('thousands', 'length')
N_ENVS = {f: len(X4.FAMILIES4[f]) for f in FAMS}               # 8 и 3
MIN_VALID = {'thousands': 6, 'length': 2}                     # опыт определён (HYPOTHESIS §5)
NONDEG_ORACLE = 0.1
POWER_MIN = 0.2                                               # ниже — правило описательно (HYPOTHESIS §5)
Z = P.Z
K_POINT, K_BOOT = O3.K_POINT, O3.K_BOOT                       # 1000 и 10 перестановок, как в OCDIV-02 и OCDIV-03
B_TEST, B_PILOT = 10_000, 1000
RULES = {'Р1-Т': ('thousands', 'd3c_ood', 'pos', True), 'Р1-Л': ('length', 'd3c_ood', 'pos', False),
         'Р2-Т': ('thousands', 'k_diff', 'two', True)}           # правило: (семейство, величина, вид, есть ли часть Б)
DESCR = ('d3c_id', 'k_ood', 'k_id', 't4_ood', 'd3u_ood', 'd3c_diff', 'rel_ood', 'n0c_ood', 'd3c_ood')
# вброс (ПОЛОЖИТЕЛЬНЫЙ-КОНТРОЛЬ-N3): у доли δ неверных ответов каждой головы смещение — общее для задачи −10^(1 + (a + b) mod 3)
SPIKE_DELTAS = (0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4)
SPIKE_TARGETS = (0.01, 0.02)                                   # заложенный прирост Δ3c (по суждению, HYPOTHESIS §7)
SPIKE_FIT_MIN = 0.8                                            # мощность Р1-Т при приросте +0,02 ниже — N3c не годится
# зёрна OCDIV-04 (+ смещение среды off4); повтор бутстрепа — своё зерно + 5000
SEED_CV4 = 9_490_000
STREAMS = {'d3c_ood': 0, 'd3c_id': 1, 'k_ood': 2, 'k_id': 3, 't4_ood': 4, 'd3u_ood': 5, 'pairs': 6, 'spike': 7, 'spike_items': 8, 'n0c_ood': 9}
# HYPOTHESIS-ADDENDUM.md (после пилота, до повторного разбора): ВБРОС-ПО-ЗАДАЧАМ — на доле δ задач вне диапазона все неверные числовые
# ответы голов получают общее для задачи смещение; естественные совпадения на других задачах не трогаются. Правило годности — прежнее.
SPIKE_ITEM_DELTAS = (0.005, 0.01, 0.02, 0.05, 0.1, 0.15, 0.2)
SEED_TEST, SEED_PILOT = 9_500_000, 9_600_000
SEED_POWER4, SEED_REP4 = 9_710_000, 9_720_000
K_PAIRS = 200
# константы PREREG (по разбору пилота и третьему контролю, до данных теста). Источники сверяет тест test_ocdiv4.py (замок «константы ↔ json»):
# N3C_FIT — gha_out/ocdiv4_control3/control3.json (n3c_fit; HYPOTHESIS-ADDENDUM-2: в T_X49_p3 нет корня — контроль не пройден);
# RULES_ACTIVE — решающая мощность по пилоту при первичном нуле не меньше POWER_MIN (gha_out/ocdiv4_sum_pilot3/pilot.json: power_alt для Р1
# при N0c, power для Р2-Т); NONDEG — pilot.json, nondeg (оракул ≥ 0,1).
RULES_ACTIVE = {'Р1-Т': False, 'Р1-Л': True, 'Р2-Т': False}
NONDEG = {'thousands': ['T_X19_p3', 'T_X29_p3', 'T_X39_p3', 'T_X49_p3', 'T_X59_p3', 'T_X69_p3', 'T_X79_p3', 'T_X89_p3'],
          'length': ['L_X9_p3', 'L_X99_p3', 'L_X999_p3']}
N3C_FIT = False            # True — N3c годен; False — первичный нуль Р1 — N0 со стратами c1 (N0c), N3c — ветвь (описательно)


def primary_key(rule, n3c_fit):
    """Величина правила при первичном нуле: у Р1 — Δ3c (N3c) при годном N3c, иначе Δ0c (N0c); у Р2-Т — K вне минус ID."""
    key = RULES[rule][1]
    return ('d3c_ood' if n3c_fit else 'n0c_ood') if key == 'd3c_ood' else key


def primary_power(pilot_res, rule, n3c_fit):
    """Запись мощности по пилоту при первичном нуле (power_entry4): у Р1 при N0c — power_alt «R (N0c)», иначе — power."""
    if RULES[rule][1] == 'd3c_ood' and not n3c_fit:
        return pilot_res['power_alt'][rule + ' (N0c)']
    return pilot_res['power'][rule]


def decisive(pw_entry, kind, tau_hi=False):
    """Решающая мощность: у двустороннего правила — вверх + вниз (ERRORS № 202), у одностороннего — «подтверждено»."""
    p = pw_entry['power_tau_hi' if tau_hi else 'power']
    return p['confirm'] + p['refute'] if kind == 'two' else p['confirm']


def seed_of(test, stream, o):
    return (SEED_TEST if test else SEED_PILOT) + 10_000 * STREAMS[stream] + o


def test_id_count(fam, X):
    """Число задач ID в среде теста — по строению среды (ответы не читаются); масштаб порогов проверки метода."""
    e = [x for x in X4.envs_ocdiv4('test3', (fam,)) if int(x['X']) == int(X)][0]
    return sum(p['range'] == 'ID' for p in e['problems'])


def planted(probs, j):
    a, b = probs[j]['a'], probs[j]['b']
    return -(10 ** (1 + (a + b) % 3))


def spike(D, probs, cols, delta, rng):
    """Вброс: у доли delta неверных числовых ответов каждой головы смещение заменяется общим для задачи (по слагаемым)."""
    Ds = D.copy()
    pl = np.array([planted(probs, j) for j in cols], dtype=np.int64)
    for k in range(D.shape[1]):
        w = np.nonzero(wrong_num(D[:, k:k + 1])[:, 0])[0]
        m = int(round(delta * len(w)))
        if m:
            pick = rng.choice(w, m, replace=False)
            Ds[pick, k] = pl[pick]
    return Ds


def spike_items(D, probs, cols, delta, rng):
    """ВБРОС-ПО-ЗАДАЧАМ (HYPOTHESIS-ADDENDUM): доля delta задач; на каждой все неверные числовые ответы — общее для задачи смещение."""
    Ds = D.copy()
    m = int(round(delta * D.shape[0]))
    if m:
        rows = rng.choice(D.shape[0], m, replace=False)
        wr = wrong_num(D)
        for j in rows:
            Ds[j, wr[j]] = planted(probs, cols[j])
    return Ds


def pair_excess4(D, strata, rng, K):
    """По парам: доля совпавших смещений при совместной ошибке минус то же при N3c (для ОТРИЦАТЕЛЬНОГО-КОНТРОЛЯ-ПАРЫ)."""
    h = D.shape[1]
    obs = pair_counts(D)
    acc = np.zeros(len(obs))
    for _ in range(K):
        acc += np.array([s / c if c else np.nan for c, s in pair_counts(permute_wrong(D, rng, strata))])
    r = np.full((h, h), np.nan)
    for (i, j), (c, s), a0 in zip(itertools.combinations(range(h), 2), obs, acc / K):
        if c:
            r[i, j] = r[j, i] = s / c - a0
    return r


def env4(job):
    """Одна среда: толпа по проверке метода (только ID), Δ3c и K вне диапазона и на ID, вторичные меры, пары; на пилоте — вброс."""
    env, test, n_id_test, B, K_point, K_boot, with_spike = job
    o = off4(env['meta'])
    st, info = W.prepare_id(env, SEED_CV4 + o, n_id_test)
    keep = info['keep']
    names = [O3.short(info['names'][k]) for k in keep]
    out = dict(crowd=names, valid=bool(info['valid']), n_id=int(info['rid'].sum()), n_ood=int((~info['rid']).sum()),
               method={O3.short(k): v for k, v in info['method'].items()})
    if not info['valid']:
        return out
    probs = env['problems']
    sums = [p['sum'] for p in probs]
    ans = [info['ans'][k] for k in keep]
    cols = {'ood': list(info['ood']), 'id': list(info['idi'])}
    D = {r: W.dmat(ans, sums, c) for r, c in cols.items()}
    sc = {r: strata_c1(probs, c) for r, c in cols.items()}
    boots = {}
    for r in ('ood', 'id'):
        out[f'd3c_{r}'], boots[f'd3c_{r}'] = d3c_stream(D[r], sc[r], seed_of(test, f'd3c_{r}', o), seed_of(test, f'd3c_{r}', o) + 5000,
                                                       B, K_point, K_boot)
        out[f'k_{r}'], boots[f'k_{r}'] = k_stream(D[r], sc[r], seed_of(test, f'k_{r}', o), seed_of(test, f'k_{r}', o) + 5000, B, K_point, K_boot)
        out[f'strata_{r}'] = {int(s): int((sc[r] == s).sum()) for s in np.unique(sc[r])}
    out['t4_ood'], boots['t4_ood'] = O3.t4_stream(D['ood'], None, seed_of(test, 't4_ood', o), seed_of(test, 't4_ood', o) + 5000, B, K_point, K_boot)
    # запасной нуль по букве HYPOTHESIS §7 (если N3c «не годен»): N0 со стратами c1 — `ocdiv3.t4_stream` со стратами c1 (перестановка всех
    # смещений головы, верных и неверных, внутри страты); своим потоком
    out['n0c_ood'], boots['n0c_ood'] = O3.t4_stream(D['ood'], sc['ood'], seed_of(test, 'n0c_ood', o), seed_of(test, 'n0c_ood', o) + 5000, B, K_point,
                                                    K_boot)
    cu = cells_c1u(probs, cols['ood'])
    out['d3u_ood'], boots['d3u_ood'] = d3c_stream(D['ood'], cu, seed_of(test, 'd3u_ood', o), seed_of(test, 'd3u_ood', o) + 5000, B, K_point, K_boot)
    # производные по средам (повторы — независимые потоки двух областей, строки ID и вне диапазона не пересекаются)
    out['k_diff'] = dict(point=out['k_ood']['point'] - out['k_id']['point'], sd=float(np.std(boots['k_ood'] - boots['k_id'], ddof=1)))
    boots['k_diff'] = boots['k_ood'] - boots['k_id']
    out['d3c_diff'] = dict(point=out['d3c_ood']['point'] - out['d3c_id']['point'], sd=float(np.std(boots['d3c_ood'] - boots['d3c_id'], ddof=1)))
    boots['d3c_diff'] = boots['d3c_ood'] - boots['d3c_id']
    f0 = out['d3c_ood']['F0']
    out['rel_ood'] = dict(point=(out['d3c_ood']['point'] / f0) if f0 > 0 else float('nan'), sd=float('nan'))
    out['oracle_ood'] = float(st['corr'][keep][:, cols['ood']].any(0).mean())
    out['kinds_ood'] = {nm: kinds_of_head(D['ood'][:, k]) for k, nm in enumerate(names)}
    out['same_pairs_ood'] = same_pairs_by_kind(D['ood'])
    cells = O3.extra_token_cells(env, names, cols['ood'])          # прибор (как OCDIV-03): ответы с лишними токенами
    fix = None
    if cells:                                                      # описательно: такие ответы — «без числа», вердикт — по основному счёту
        Df = D['ood'].copy()
        for r_, k in cells:
            Df[r_, k] = NC + k
        fix = dict(n_cells=len(cells), d3c=d3c_point(Df, sc['ood'], np.random.default_rng(seed_of(test, 'spike', o) + 2), K_point)[2])
    out['extra_tokens'] = dict(n_cells=len(cells), recount=fix)
    r = pair_excess4(D['ood'], sc['ood'], np.random.default_rng(seed_of(test, 'pairs', o)), K_PAIRS)
    out['pairs'] = dict(crowd=names, r=[[None if not np.isfinite(x) else float(x) for x in row] for row in r])
    if with_spike:
        g = np.random.default_rng(seed_of(test, 'spike', o))
        base = d3c_point(D['ood'], sc['ood'], np.random.default_rng(seed_of(test, 'spike', o) + 1), K_point)[2]
        out['spike'], out['spike_k'] = {}, {}
        k0 = k_raw(D['ood'])
        for dl in SPIKE_DELTAS:
            Ds = spike(D['ood'], probs, cols['ood'], dl, g)
            out['spike'][str(dl)] = d3c_point(Ds, sc['ood'], np.random.default_rng(seed_of(test, 'spike', o) + 1), K_point)[2] - base
            out['spike_k'][str(dl)] = k_raw(Ds) - k0           # ERRORS № 201: ломает ли вброс естественные совпадения (K падает)
        gi = np.random.default_rng(seed_of(test, 'spike_items', o))
        out['spike_items'] = {}
        for dl in SPIKE_ITEM_DELTAS:
            Ds = spike_items(D['ood'], probs, cols['ood'], dl, gi)
            out['spike_items'][str(dl)] = d3c_point(Ds, sc['ood'], np.random.default_rng(seed_of(test, 'spike', o) + 1), K_point)[2] - base
    out['_boot'] = boots
    return out


def pmap4(jobs, workers):
    if workers <= 1:
        return [env4(j) for j in jobs]
    with cf.ProcessPoolExecutor(workers) as ex:
        return list(ex.map(env4, jobs))


def env_signs(points, sds, names):
    """Знак по средам: интервал среды при уровне 0,0025 / n (n — число сред правила) целиком > 0, < 0 или накрывает 0."""
    z_env = float(norm.ppf(1 - LEVEL / max(len(names), 1)))
    out = dict(z_env=z_env, pos=[], neg=[], zero=[])
    for n in names:
        lo, hi = points[n] - z_env * sds[n], points[n] + z_env * sds[n]
        out['pos' if lo > 0 else 'neg' if hi < 0 else 'zero'].append(n)
    return out


def rule4(points, boots, sds, names, kind, part_b):
    """Правило из двух частей (HYPOTHESIS §5): А — M4 среднего сред при 0,0025; Б — t по средам (df = n − 1) против t(0,9975; n − 1)."""
    e = mean_entry(points, boots, names, LEVEL)
    tb = t_envs({n: points[n] for n in names})
    e['t_envs'] = tb
    e['signs'] = env_signs(points, sds, names)
    a = e['verdict']                                        # pos: «подтверждено» — низ > 0, «опровергнуто» — верх < 0
    b_up = np.isfinite(tb['t']) and tb['t'] > tb['crit']
    b_dn = np.isfinite(tb['t']) and tb['t'] < -tb['crit']
    if kind == 'pos':
        if a == 'подтверждено' and (b_up or not part_b):
            v = 'подтверждено'
        elif a == 'опровергнуто' and (b_dn or not part_b):
            v = 'опровергнуто'
        elif a == 'подтверждено':
            v = 'в среднем этих сред (на новые среды не переносится)'
        else:
            v = 'не решено'
    else:                                                    # двусторонний: направление — по знаку
        if a == 'подтверждено' and b_up:
            v = 'вне диапазона больше'
        elif a == 'опровергнуто' and b_dn:
            v = 'вне диапазона меньше'
        elif a in ('подтверждено', 'опровергнуто'):
            v = 'в среднем этих сред: ' + ('вне диапазона больше' if a == 'подтверждено' else 'вне диапазона меньше') + ' (на новые среды не переносится)'
        else:
            v = 'не решено'
    e['verdict_rule'] = v
    e['mark'] = 'знак по средам разный' if (e['signs']['neg'] and e['signs']['pos']) else None
    return e


def power4(mu, tau, s, m, part_b, n=200_000, seed=SEED_POWER4):
    """Мощность правила: точка среды ~ N(mu, tau² + s²); А — среднее ± z·s/√m; Б — t по m средам против t(0,9975; m − 1)."""
    g = np.random.default_rng(seed)
    x = g.normal(mu, np.sqrt(tau ** 2 + s ** 2), size=(n, m))
    mean, sd = x.mean(1), x.std(1, ddof=1)
    h = Z * s / np.sqrt(m)
    t = mean / (sd / np.sqrt(m))
    crit = float(student_t.ppf(1 - LEVEL, m - 1))
    a_up, a_dn = mean - h > 0, mean + h < 0
    up = a_up & (t > crit) if part_b else a_up
    dn = a_dn & (t < -crit) if part_b else a_dn
    return dict(confirm=float(up.mean()), refute=float(dn.mean()), part_a=float(a_up.mean()), part_b=float((t > crit).mean()), crit=crit)


def power_entry4(points, sds, scale, m, part_b, mu=None):
    x, sp = np.asarray(points, float), np.asarray(sds, float)
    ok = np.isfinite(x) & np.isfinite(sp)
    x, sp = x[ok], sp[ok]
    if len(x) < 2:
        return None
    s_test = float(np.sqrt(np.mean(sp ** 2)) * scale)
    tau = float(np.sqrt(max(0.0, x.var(ddof=1) - np.mean(sp ** 2))))
    var_hi = (len(x) - 1) * x.var(ddof=1) / float(chi2.ppf(0.025, len(x) - 1))
    tau_hi = float(np.sqrt(max(0.0, var_hi - np.mean(sp ** 2))))
    mu_ = float(x.mean()) if mu is None else float(mu)
    return dict(n_envs=int(len(x)), mu=mu_, tau=tau, tau_hi=tau_hi, s_pilot_rms=float(np.sqrt(np.mean(sp ** 2))), s_test=s_test, scale=scale,
                power=power4(mu_, tau, s_test, m, part_b), power_tau_hi=power4(mu_, tau_hi, s_test, m, part_b))


def load_family(mdir):
    d, envs = S.load_new(mdir)
    hm = {h['model']: h for h in d['heads']}
    names_c, dropped = V.effective_crowd(hm)
    return d, envs, names_c, dropped


def family_jobs(envs, names_c, test, B, with_spike):
    order = sorted(envs, key=lambda n: int(envs[n]['meta']['X']))
    jobs = []
    for n in order:
        env = envs[n]
        meta = env['meta']
        env_c = dict(env, heads=[h for h in env['heads'] if h['model'] in names_c])
        jobs.append((env_c, test, test_id_count(meta['family'], meta['X']), B, K_POINT, K_BOOT, with_spike))
    return order, jobs


def run_family(mdir, test, B, workers, with_spike):
    d, envs, names_c, dropped = load_family(mdir)
    order, jobs = family_jobs(envs, names_c, test, B, with_spike)
    outs = pmap4(jobs, workers)
    res, boots = {}, {}
    for n, r in zip(order, outs):
        r['meta'] = {k: envs[n]['meta'][k] for k in ('family', 'X', 'p', 'bound', 'max_new')}
        boots[n] = r.pop('_boot', {})
        res[n] = r
    return res, boots, dict(crowd_effective=names_c, crowd_dropped=dropped, head_errors=d.get('head_errors', []), keys_checked=d.get('keys_checked'))


def contrast4(rmaps, struct):
    """Как `ocdiv3.contrast`, но пары без совместной ошибки (r = NaN) не входят в средние."""
    vals = []
    for crowd, r in rmaps:
        same, cross = [], []
        for i, j in itertools.combinations(range(len(crowd)), 2):
            if np.isfinite(r[i, j]):
                (same if frozenset({crowd[i], crowd[j]}) in struct else cross).append(r[i, j])
        if same and cross:
            vals.append(np.mean(same) - np.mean(cross))
    return float(np.mean(vals)) if vals else float('nan')


def pairs_contrast(rmaps):
    """ОТРИЦАТЕЛЬНЫЙ-КОНТРОЛЬ-ПАРЫ: контраст «пары одного производителя − пары разных» по r при совместной ошибке; точный перебор
    105 структур (`ocdiv3.structures`), наблюдённая — `ocdiv3.OBSERVED_PAIRS`; описательно, наименьшее p = 1/105."""
    obs = contrast4(rmaps, O3.OBSERVED_PAIRS)
    allc = [contrast4(rmaps, st) for st in O3.structures(list(CROWD))]
    fin = [c for c in allc if np.isfinite(c)]
    return dict(observed=obs, n_structures=len(allc), p_exact=(float(np.mean([c >= obs - 1e-15 for c in fin])) if fin and np.isfinite(obs) else None),
                null_mean=(float(np.mean(fin)) if fin else None))


def versions():
    return dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__)


def pilot4(dst, mdirs, B=B_PILOT, workers=1):
    """Разбор пилота: невырожденность сред, мощность Р1-Т, Р1-Л, Р2-Т (частей А и Б), вброс и годность N3c, ожидания. Данные теста не читаются."""
    t0 = time.time()
    res = dict(phase='pilot3', hypothesis='7aed3606', B=B, K_point=K_POINT, K_boot=K_BOOT, versions=versions(), families={})
    for fam in FAMS:
        envs, boots, meta = run_family(mdirs[fam], False, B, workers, fam == 'thousands')
        valid = [n for n in envs if envs[n]['valid']]
        nondeg = [n for n in valid if envs[n]['oracle_ood'] >= NONDEG_ORACLE]
        scale = {}
        for n in valid:
            e_test = [x for x in X4.envs_ocdiv4('test3', (fam,)) if x['name'] == n][0]
            n_ood_t = sum(p['range'] != 'ID' for p in e_test['problems'])
            n_id_t = len(e_test['problems']) - n_ood_t
            scale[n] = dict(ood=float(np.sqrt(envs[n]['n_ood'] / n_ood_t)), id=float(np.sqrt(envs[n]['n_id'] / n_id_t)))
        res['families'][fam] = dict(envs=envs, valid=valid, nondeg=nondeg, scale=scale, **meta)
    res['power'], res['power_alt'] = {}, {}
    for rule, fam, part_b in (('Р1-Т', 'thousands', True), ('Р1-Л', 'length', False)):   # запасной нуль N0c (описательно, для совета)
        F = res['families'][fam]
        use = list(F['nondeg'])
        res['power_alt'][rule + ' (N0c)'] = power_entry4([F['envs'][n]['n0c_ood']['point'] for n in use], [F['envs'][n]['n0c_ood']['sd'] for n in use],
                                                          float(np.mean([F['scale'][n]['ood'] for n in use])) if use else float('nan'), N_ENVS[fam], part_b)
    for rule, (fam, key, kind, part_b) in RULES.items():
        F = res['families'][fam]
        use = [n for n in F['nondeg']]
        pts = [F['envs'][n][key]['point'] for n in use]
        sds = [F['envs'][n][key]['sd'] for n in use]
        sc = float(np.mean([F['scale'][n]['ood'] for n in use])) if use else float('nan')
        res['power'][rule] = power_entry4(pts, sds, sc, N_ENVS[fam], part_b)
    # вброс (положительный контроль N3c): δ* — по средней кривой прироста Δ3c «тысяч» для прироста +0,01 и +0,02; прирост каждой среды
    # при δ* — линейной интерполяцией её кривой; мощность Р1-Т при заложенном приросте: среднее и разброс между средами — у заложенного
    # прироста (а не у настоящего эффекта), s — пересчёт ст. откл. Δ3c пилота на тест (как у Р1-Т). Два вброса: первоначальный
    # (HYPOTHESIS §7) и ВБРОС-ПО-ЗАДАЧАМ (HYPOTHESIS-ADDENDUM); годность N3c — по второму, первый — как записанный.
    F = res['families']['thousands']
    use = F['nondeg']
    pw = res['power']['Р1-Т']
    for key, deltas in (('spike', SPIKE_DELTAS), ('spike_items', SPIKE_ITEM_DELTAS)):
        xs = [0.0] + list(deltas)
        per = {n: [0.0] + [F['envs'][n][key][str(d)] for d in deltas] for n in use if key in F['envs'][n]}
        mean_curve = [float(np.mean([per[n][i] for n in per])) for i in range(len(xs))] if per else []
        out_sp = dict(deltas=xs, mean_curve=mean_curve, targets={})
        for tg in SPIKE_TARGETS:
            dl = None
            if mean_curve and max(mean_curve) >= tg:
                i = next(k for k, y in enumerate(mean_curve) if y >= tg)
                dl = xs[i] if i == 0 or mean_curve[i] == mean_curve[i - 1] else \
                    xs[i - 1] + (tg - mean_curve[i - 1]) * (xs[i] - xs[i - 1]) / (mean_curve[i] - mean_curve[i - 1])
            inc = [float(np.interp(dl, xs, per[n])) for n in per] if dl is not None else []
            tau_inc = float(np.std(inc, ddof=1)) if len(inc) > 1 else None
            p_tg = power4(float(np.mean(inc)), tau_inc, pw['s_test'], N_ENVS['thousands'], True) if (pw and inc and tau_inc is not None) else None
            out_sp['targets'][str(tg)] = dict(delta=dl, increments=dict(zip(per, inc)), tau_increment=tau_inc, power_at_target=p_tg)
        res[key] = out_sp
    res['spike_k_mean'] = {str(d): float(np.mean([F['envs'][n]['spike_k'][str(d)] for n in use])) for d in SPIKE_DELTAS} if use else {}
    fit = {}
    for key in ('spike', 'spike_items'):
        p2 = res[key]['targets'][str(SPIKE_TARGETS[-1])]['power_at_target']
        fit[key] = bool(p2 is not None and p2['confirm'] >= SPIKE_FIT_MIN)
    res['n3c_fit_original'] = fit['spike']
    res['n3c_fit'] = fit['spike_items']                         # HYPOTHESIS-ADDENDUM: годность — по ВБРОСУ-ПО-ЗАДАЧАМ
    for r, (_, _, kind, _) in RULES.items():                  # ERRORS № 202: у двустороннего правила вердикт — в любую сторону
        if res['power'][r] is not None:
            pw_ = res['power'][r]['power']
            pw_['decisive'] = pw_['confirm'] + pw_['refute'] if kind == 'two' else pw_['confirm']
    res['rules_active'] = {r: bool(res['power'][r] is not None and res['power'][r]['power']['decisive'] >= POWER_MIN) for r in RULES}
    res['nondeg'] = {fam: res['families'][fam]['nondeg'] for fam in FAMS}
    res['expect'] = {r: (0.95 * res['power'][r]['power']['decisive'] if res['power'][r] else None) for r in RULES}
    res['seconds'] = round(time.time() - t0, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
    print('пилот:', {r: (round(res['power'][r]['power']['confirm'], 3) if res['power'][r] else None) for r in RULES},
          '| годность N3c:', res['n3c_fit'], '| невырожденные:', res['nondeg'], '| время', res['seconds'], 'с', flush=True)
    return res


def compare_pilots(new, old, tol=0.0):
    """Повторный разбор пилота (HYPOTHESIS-ADDENDUM): всё, кроме вбросов и мощности Р2-Т, должно совпасть с первым разбором до бита."""
    bad = []
    for fam in FAMS:
        for n, e in old['families'][fam]['envs'].items():
            e2 = new['families'][fam]['envs'][n]
            for key in ('d3c_ood', 'd3c_id', 'k_ood', 'k_id', 't4_ood', 'd3u_ood'):
                if key in e and (abs(e[key]['point'] - e2[key]['point']) > tol or abs(e[key]['sd'] - e2[key]['sd']) > tol):
                    bad.append(f'{n} {key}')
            for d in SPIKE_DELTAS:
                if 'spike' in e and abs(e['spike'][str(d)] - e2['spike'][str(d)]) > tol:
                    bad.append(f'{n} spike {d}')
    for r in ('Р1-Т', 'Р1-Л', 'Р2-Т'):
        for k in ('mu', 'tau', 's_test'):
            if abs(old['power'][r][k] - new['power'][r][k]) > tol:
                bad.append(f'power {r} {k}')
        if r != 'Р2-Т' and abs(old['power'][r]['power']['confirm'] - new['power'][r]['power']['confirm']) > tol:
            bad.append(f'power {r} confirm')
    return bad


def rule_entry(F, boots, key, kind, part_b):
    """Правило по величине key на средах F['use']; вердикт «не определено», если годных сред меньше MIN_VALID."""
    use = F['use']
    pts = {n: F['envs'][n][key]['point'] for n in use}
    sds = {n: F['envs'][n][key]['sd'] for n in use}
    e = rule4(pts, {n: boots[n][key] for n in use}, sds, use, kind, part_b) if use else dict(verdict_rule='не решено')
    if not F['method_ok']:
        e['verdict_rule'] = 'не определено (годных сред мало)'
    e['key'] = key
    return e


def test4(dst, mdirs, pilot_res, B=B_TEST, workers=1):
    """Анализ теста: правила Р1-Т, Р1-Л, Р2-Т по константам PREREG; знак по средам; описательное; пары."""
    assert RULES_ACTIVE is not None and NONDEG is not None and N3C_FIT is not None, 'константы PREREG не заданы'
    t0 = time.time()
    pr = json.load(open(pilot_res, encoding='utf-8'))
    res = dict(phase='test3', level=LEVEL, z=Z, B=B, K_point=K_POINT, K_boot=K_BOOT, rules_active=RULES_ACTIVE, nondeg=NONDEG, n3c_fit=N3C_FIT,
               pilot_power={r: pr['power'][r] for r in RULES}, versions=versions(), families={})
    boots_all = {}
    for fam in FAMS:
        envs, boots, meta = run_family(mdirs[fam], True, B, workers, False)
        valid = [n for n in envs if envs[n]['valid']]
        use = [n for n in valid if n in NONDEG[fam]]
        res['families'][fam] = dict(envs=envs, valid=valid, use=use, method_ok=bool(len(use) >= MIN_VALID[fam]), **meta)
        boots_all[fam] = boots
        print(fam, ': годных', len(valid), 'из', len(envs), '| в правилах', len(use), round(time.time() - t0), 'с', flush=True)
    res['rules'], res['rules_alt'] = {}, {}
    for rule, (fam, key, kind, part_b) in RULES.items():
        F = res['families'][fam]
        prim = primary_key(rule, N3C_FIT)                         # HYPOTHESIS §7, ADDENDUM-2: N3c «не годен» — первичный нуль Р1 — N0c
        e = rule_entry(F, boots_all[fam], prim, kind, part_b)
        e['active'] = RULES_ACTIVE[rule]
        res['rules'][rule] = e
        if key == 'd3c_ood':                                      # ветвь (PREREG §5, описательно): Р1 по второму нулю тем же правилом
            alt = 'n0c_ood' if N3C_FIT else 'd3c_ood'
            ea = rule_entry(F, boots_all[fam], alt, kind, part_b)
            ea['active'] = False
            res['rules_alt'][rule] = ea
    res['descr'] = {}
    for fam in FAMS:
        F = res['families'][fam]
        for key in DESCR:
            use = [n for n in F['use'] if np.isfinite(F['envs'][n][key]['point'])]
            if key == 'rel_ood' or not use:
                res['descr'][f'{fam} {key}'] = dict(by_env={n: F['envs'][n][key]['point'] for n in use})
                continue
            res['descr'][f'{fam} {key}'] = dict(**mean_entry({n: F['envs'][n][key]['point'] for n in use}, {n: boots_all[fam][n][key] for n in use},
                                                             use, DESCR_LEVEL), t_envs=t_envs({n: F['envs'][n][key]['point'] for n in use}))
    rm = [(res['families'][f]['envs'][n]['pairs']['crowd'], np.array([[np.nan if x is None else x for x in row]
                                                                      for row in res['families'][f]['envs'][n]['pairs']['r']]))
          for f in FAMS for n in res['families'][f]['use']]
    res['pairs'] = pairs_contrast(rm) if rm else None
    res['repeat_check'] = W.repeat_check(os.path.join(ROOT, 'gha_out/ocdiv4_test_*/answers_*.json'), os.path.join(ROOT, 'gha_out/ocdiv4_rep_*/answers_*.json'))
    res['verdicts'] = {r: res['rules'][r]['verdict_rule'] for r in RULES}
    res['seconds'] = round(time.time() - t0, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
    print('вердикт:', res['verdicts'], '| время', res['seconds'], 'с', flush=True)
    return res


# ═══════════════ часть 3: третий положительный контроль N3c (HYPOTHESIS-ADDENDUM-2, совет 72)
C3_GRID = (0.005, 0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4)
C3_R = 20
C3_TARGET = 0.02
C3_SLOPE = (0.8, 1.2)
C3_POWER_MIN = 0.8
SEED_SPLIT3, SEED_ASSIGN3 = 9_730_000, 9_740_000
SEED_NULL3, SEED_H1, SEED_H2 = 9_750_000, 9_760_000, 9_770_000


def c3_env(env, n_id_test):
    """Толпа и матрица смещений вне диапазона — как в env4; разбиение задач вне диапазона на Н1 и Н2 зерном SEED_SPLIT3 + смещение."""
    o = off4(env['meta'])
    st, info = W.prepare_id(env, SEED_CV4 + o, n_id_test)
    if not info['valid']:
        return None
    probs = env['problems']
    ans = [info['ans'][k] for k in info['keep']]
    cols = list(info['ood'])
    D = W.dmat(ans, [p['sum'] for p in probs], cols)
    sc = strata_c1(probs, cols)
    perm = np.random.default_rng(SEED_SPLIT3 + o).permutation(len(cols))
    h1, h2 = np.sort(perm[:len(cols) // 2]), np.sort(perm[len(cols) // 2:])
    half = lambda idx: (D[idx], sc[idx], [cols[i] for i in idx])  # noqa: E731
    return dict(o=o, probs=probs, h1=half(h1), h2=half(h2), n=len(cols))


def c3_increment(Dh, sh, ch, probs, delta, seed_place, base_seed):
    """Прирост Δ3c при ВБРОСЕ-ПО-ЗАДАЧАМ на половине: общее зерно нуля у Δ3c с вбросом и без (общие случайные числа)."""
    base = d3c_point(Dh, sh, np.random.default_rng(base_seed), K_POINT)[2]
    Ds = spike_items(Dh, probs, ch, delta, np.random.default_rng(seed_place))
    return d3c_point(Ds, sh, np.random.default_rng(base_seed), K_POINT)[2] - base


def c3_curve_job(job):
    env, n_id_test, R = job
    e = c3_env(env, n_id_test)
    if e is None:
        return None
    Dh, sh, ch = e['h1']
    o = e['o']
    curve = []
    for k, dl in enumerate(C3_GRID):
        curve.append(float(np.mean([c3_increment(Dh, sh, ch, e['probs'], dl, SEED_H1 + 100_000 * k + 1000 * r + o, SEED_NULL3 + 1000 * r + o)
                                    for r in range(R)])))
    return dict(n_ood=e['n'], n_h1=int(Dh.shape[0]), n_h2=int(e['h2'][0].shape[0]), curve=curve)


def c3_control_job(job):
    env, n_id_test, R, dl = job
    e = c3_env(env, n_id_test)
    if e is None or dl is None:
        return None
    Dh, sh, ch = e['h2']
    o = e['o']
    return float(np.mean([c3_increment(Dh, sh, ch, e['probs'], dl, SEED_H2 + 1000 * r + o, SEED_NULL3 + 1000 * r + o + 500) for r in range(R)]))


def c3_targets(tau, names):
    """t_i = 0,02 + τ·Φ⁻¹((i − 0,5)/8), i = 1…8; среде с номером j (порядок X) — цель t[perm[j]], perm — permutation(8) от SEED_ASSIGN3."""
    t = [C3_TARGET + tau * float(norm.ppf((i - 0.5) / len(names))) for i in range(1, len(names) + 1)]
    perm = np.random.default_rng(SEED_ASSIGN3).permutation(len(names))
    return {n: t[int(perm[j])] for j, n in enumerate(names)}


def c3_root(curve, target):
    """δ_e — первое пересечение уровня цели при линейной интерполяции по возрастанию дозы от (0; 0); нет пересечения — None (провал среды)."""
    xs, ys = [0.0] + list(C3_GRID), [0.0] + list(curve)
    for k in range(1, len(xs)):
        if ys[k - 1] < target <= ys[k]:
            return xs[k - 1] + (target - ys[k - 1]) * (xs[k] - xs[k - 1]) / (ys[k] - ys[k - 1])
    return None


def c3_pmap(fn, jobs, workers):
    if workers <= 1:
        return [fn(j) for j in jobs]
    with cf.ProcessPoolExecutor(workers) as ex:
        return list(ex.map(fn, jobs))


def curves3(dst, mdir, pilot_res, R=C3_R, workers=1):
    """Задание 1 третьего контроля: кривые «доза–прирост» на Н1, цели, δ_e. Данные теста не читаются."""
    t0 = time.time()
    pr = json.load(open(pilot_res, encoding='utf-8'))
    d, envs, names_c, _ = load_family(mdir)
    order = sorted(envs, key=lambda n: int(envs[n]['meta']['X']))
    jobs = [(dict(envs[n], heads=[h for h in envs[n]['heads'] if h['model'] in names_c]), test_id_count('thousands', envs[n]['meta']['X']), R)
            for n in order]
    outs = c3_pmap(c3_curve_job, jobs, workers)
    tau = pr['power']['Р1-Т']['tau']
    tg = c3_targets(tau, order)
    res = dict(what='OCDIV-04, третий контроль N3c — задание 1 (кривые на Н1; HYPOTHESIS-ADDENDUM-2)', grid=list(C3_GRID), R=R, tau=tau,
               s_test=pr['power']['Р1-Т']['s_test'], targets=tg, envs={})
    for n, out in zip(order, outs):
        res['envs'][n] = dict(**(out or {}), target=tg[n], delta=(c3_root(out['curve'], tg[n]) if out else None))
    res['all_roots'] = all(res['envs'][n].get('delta') is not None for n in order)
    res['seconds'] = round(time.time() - t0, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
    print('кривые:', {n: (None if res['envs'][n]['delta'] is None else round(res['envs'][n]['delta'], 4)) for n in order},
          '| все корни:', res['all_roots'], '| время', res['seconds'], 'с', flush=True)
    return res


def control3(dst, mdir, curves_res, R=C3_R, workers=1):
    """Задание 2 третьего контроля: реализованный прирост на Н2 при δ_e из задания 1; критерий годности N3c (HYPOTHESIS-ADDENDUM-2)."""
    t0 = time.time()
    cr = json.load(open(curves_res, encoding='utf-8'))
    d, envs, names_c, _ = load_family(mdir)
    order = sorted(envs, key=lambda n: int(envs[n]['meta']['X']))
    jobs = [(dict(envs[n], heads=[h for h in envs[n]['heads'] if h['model'] in names_c]), test_id_count('thousands', envs[n]['meta']['X']), R,
             cr['envs'][n]['delta']) for n in order]
    outs = c3_pmap(c3_control_job, jobs, workers)
    real = {n: v for n, v in zip(order, outs)}
    ok_roots = cr['all_roots'] and all(v is not None for v in real.values())
    res = dict(what='OCDIV-04, третий контроль N3c — задание 2 (проверка на Н2; HYPOTHESIS-ADDENDUM-2)', R=R, curves=os.path.relpath(curves_res, ROOT),
               targets=cr['targets'], deltas={n: cr['envs'][n]['delta'] for n in order}, realized=real, all_roots=ok_roots)
    if ok_roots:
        x = np.array([cr['targets'][n] for n in order])
        y = np.array([real[n] for n in order])
        slope = float(np.polyfit(x, y, 1)[0])
        pw = power4(float(y.mean()), float(np.std(y, ddof=1)), cr['s_test'], len(order), True)
        res.update(slope=slope, realized_mean=float(y.mean()), realized_sd=float(np.std(y, ddof=1)), power=pw)
        res['pass'] = bool(C3_SLOPE[0] <= slope <= C3_SLOPE[1] and pw['part_a'] >= C3_POWER_MIN and pw['part_b'] >= C3_POWER_MIN)
    else:
        res['pass'] = False
    res['n3c_fit'] = res['pass']
    res['seconds'] = round(time.time() - t0, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
    print('контроль:', {k: res.get(k) for k in ('slope', 'realized_mean', 'pass')}, '| время', res['seconds'], 'с', flush=True)
    return res


def main():
    a = sys.argv[1:]
    mode = a[0]
    opt = lambda k, d: (type(d)(a[a.index(k) + 1]) if k in a else d)  # noqa: E731
    if mode == 'merge':
        merge4(a[1], a[2], a[3], a[4:])
    elif mode == 'pilot':
        pilot4(a[1], {'thousands': a[2], 'length': a[3]}, B=opt('--boot', B_PILOT), workers=opt('--workers', 1))
    elif mode == 'curves3':
        curves3(a[1], a[2], a[3], R=opt('--R', C3_R), workers=opt('--workers', 1))
    elif mode == 'control3':
        control3(a[1], a[2], a[3], R=opt('--R', C3_R), workers=opt('--workers', 1))
    elif mode == 'compare_pilots':
        bad = compare_pilots(json.load(open(a[1], encoding='utf-8')), json.load(open(a[2], encoding='utf-8')))
        print('сверка разборов пилота:', 'расхождения ' + str(bad[:20]) if bad else 'совпало до бита (кроме вбросов и мощности Р2-Т)')
        sys.exit(1 if bad else 0)
    elif mode == 'test':
        test4(a[1], {'thousands': a[2], 'length': a[3]}, a[4], B=opt('--boot', B_TEST), workers=opt('--workers', 1))
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
