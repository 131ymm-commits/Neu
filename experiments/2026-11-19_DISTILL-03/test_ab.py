#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-03: тесты ab.py на заглушках с известным знаком (ворота CLAUDE.md: направленные слова, мутанты до прогона).
  python3 test_ab.py   — печатает ✓/✗ и «провалов: N»"""
import itertools
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ab  # noqa: E402

D2 = ab.D2
FAILS = []


def check(name, cond, info=''):
    print(('✓ ' if cond else '✗ ') + name + (f' — {info}' if info else ''), flush=True)
    if not cond:
        FAILS.append(name)


# ───────────── перестановочный тест
def t_perm():
    k = 7
    rng = np.random.default_rng(1)
    s = rng.normal(0, 0.01, (k, k)) + np.eye(k) * 1.0                       # сильная диагональ
    r = ab.perm_test(s)
    check('сильная диагональ: ранг 1 из 5040, p = 1/5040', r['rank'] == 1 and abs(r['p'] - 1 / 5040) < 1e-12, f"p {r['p']:.6f}")
    rows, cols = rng.normal(0, 1, k), rng.normal(0, 1, k)
    s2 = rows[None, :] + cols[:, None]                                        # только суммы строк и столбцов
    r2 = ab.perm_test(s2)
    check('аддитивная матрица: все D_π равны, p = 1', abs(r2['p'] - 1.0) < 1e-12 and abs(r2['perm_max'] - r2['D']) < 1e-9)
    ps = [ab.perm_test(rng.normal(0, 1, (k, k)))['p'] for _ in range(400)]  # нуль: p равномерно (с шагом 1/5040)
    check('нуль: доля p ≤ 0,05 около 0,05', abs(np.mean(np.array(ps) <= 0.05) - 0.05) < 0.035, f"{np.mean(np.array(ps) <= 0.05):.3f}")
    check('нуль: среднее p около 0,5', abs(np.mean(ps) - 0.5) < 0.06, f"{np.mean(ps):.3f}")


def t_s_table():
    M1 = np.array([[1.0, 0.0], [0.0, 1.0]])
    M2 = np.array([[3.0, np.nan], [1.0, np.nan]])                            # во второй среде голова 1 отсутствует
    s = ab.s_table([M1, M2])
    # s[a, b]: среда 1 — L − (S − L)/(k − 1) = [[1, −1], [−1, 1]]; среда 2, столбец 0 — [3 − 1, 1 − 3] = [2, −2]
    check('s_table: среднее по средам головы, NaN пропускаются', np.allclose(s, [[1.5, -1.0], [-1.5, 1.0]]), str(s.tolist()))


# ───────────── подбор свободного члена и строки формулы
def items_pool(n, rng, lo=1900, hi=1999):
    out = []
    for _ in range(n):
        a = int(rng.integers(lo, hi + 1))
        b = int(rng.integers(10, 999))
        out.append(dict(a=a, b=b, sum=a + b, ood=int(a + b >= 2000)))
    return out


def t_intercept():
    rng = np.random.default_rng(2)
    items = items_pool(3000, rng)
    rows, y = [], []
    for it in items:
        for r in D2.position_features(it['a'], it['b'], it['ood']):
            z = -1.0 + 0.8 * r['prop']
            rows.append(r)
            y.append(float(rng.random() < 1 / (1 + math.exp(-z))))
    b0 = ab.fit_intercept(rows, np.array(y), ['prop'], [0.8])
    check('свободный член при заданном наклоне восстановлен', abs(b0 - (-1.0)) < 0.15, f'{b0:.3f}')
    w, _ = D2.logit_fit(np.array([[r['prop']] for r in rows], float), np.array(y))
    b1 = ab.fit_intercept(rows, np.array(y), ['prop'], [w[1]])
    check('при наклоне полной подгонки свободный член совпадает с ней', abs(b1 - w[0]) < 1e-6, f'{b1:.6f} против {w[0]:.6f}')


def t_rows_match_fit_program():
    rng = np.random.default_rng(3)
    items = items_pool(1500, rng)
    prog = dict(eps=0.1, q={-80: 0.6, -90: 0.4}, q_rest=0.0, features=['prop'], w=[-1.5, 0.9], w_round=[-1.5, 0.9])
    offs = np.array([D2.sample_program(prog, it, rng) for it in items])
    fp = D2.fit_program(items, offs, fixed=('prop',))
    rows, y = ab.program_rows(items, offs)
    w, _ = D2.logit_fit(np.array([[r['prop']] for r in rows], float), y)
    check('строки формулы те же, что в fit_program', len(y) == fp['n_rows'] and np.allclose(w, fp['w'], atol=1e-9), f"{len(y)} строк")


def t_large_slopes():
    """Ошибка № 224: при наклонах ±20 свободный член должен находиться, а своя форма при своём уровне — совпадать со своей программой."""
    rng = np.random.default_rng(4)
    items = items_pool(3000, rng)
    rows, y = [], []
    for it in items:
        for r in D2.position_features(it['a'], it['b'], it['ood']):
            z = 17.0 - 23.0 * r['top'] - 22.0 * r['ood']
            rows.append(r)
            y.append(float(rng.random() < 1 / (1 + math.exp(-max(-30, min(30, z))))))
    b0 = ab.fit_intercept(rows, np.array(y), ['top', 'ood'], [-23.0, -22.0])
    check('большие наклоны: свободный член найден (около 17)', abs(b0 - 17.0) < 2.0, f'{b0:.3f}')
    prog = mk(0.1, 17.0, ['top', 'ood'], [-23.0, -22.0])
    offs = np.array([D2.sample_program(prog, it, rng) for it in items])
    P = ab.programs_from(items, {'h0': offs, 'h1': offs.copy()})
    own = P['prog']['h0']
    sh = P['shape'][('h0', 'h0')]
    ll_p, ll_s = [], []
    for it, d in zip(items[:800], offs[:800]):
        if d >= D2.NC:
            continue
        y_ = it['sum'] + int(d)
        ll_p.append(D2.mlog(D2.answer_prob(own, it, y_, True), it['sum']))
        ll_s.append(D2.mlog(D2.answer_prob(sh, it, y_, True), it['sum']))
    check('большие наклоны: своя форма при своём уровне ≈ своя программа', abs(np.mean(ll_s) - np.mean(ll_p)) < 0.05,
          f'{np.mean(ll_s):.4f} против {np.mean(ll_p):.4f}')


def t_loader_keeps_phases():
    """Ошибка № 224: одна среда в двух фазах — обе в построении (список, не словарь)."""
    orig = D2.load_merged
    try:
        D2.load_merged = lambda d: {'T_X19_p3': {'phase': d}, 'L_X9_p3': {'phase': d}}
        envs = ab.load_family_envs(['ф1', 'ф2'], 'thousands')
    finally:
        D2.load_merged = orig
    check('сборка построения: одна среда из двух фаз — обе, чужое семейство отброшено', [e['phase'] for _, e in envs] == ['ф1', 'ф2'], str(envs))


# ───────────── сквозные заглушки: головы из известных программ
def synth(progs, n_con, n_env, n_envs, seed):
    rng = np.random.default_rng(seed)
    con = items_pool(n_con, rng)
    offs_c = {h: np.array([D2.sample_program(p, it, rng) for it in con]) for h, p in progs.items()}
    envs = {}
    for e in range(n_envs):
        it_e = items_pool(n_env, rng)
        envs[f'E{e}'] = (it_e, {h: np.array([D2.sample_program(p, it, rng) for it in it_e]) for h, p in progs.items()})
    P = ab.programs_from(con, offs_c)
    return ab.family_result(P, envs, sorted(envs), sorted(progs))


def mk(eps, b0, feats, slopes):
    return dict(eps=eps, q={-80: 0.5, -90: 0.3, 10: 0.2}, q_rest=0.0, features=list(feats), w=[b0] + list(slopes), w_round=[b0] + list(slopes))


def t_end_to_end():
    H = [f'h{i}' for i in range(7)]
    # 1) только уровень разный (одна форма): программа — своя, форма — нет
    lv = {h: mk(0.03 + 0.04 * i, -2.5 + 0.45 * i, ['prop'], [1.2]) for i, h in enumerate(H)}
    r = synth(lv, 2500, 900, 3, 11)
    check('уровень разный, форма одна: программа своя (p ≤ 0,01)', r['prog']['p'] <= 0.01 and r['prog']['D'] > 0, f"D {r['prog']['D']:.4f}, p {r['prog']['p']:.4f}")
    check('уровень разный, форма одна: форма НЕ своя (p > 0,05)', r['shape']['p'] > 0.05, f"D {r['shape']['D']:.5f}, p {r['shape']['p']:.4f}")
    # 2) форма разная, уровень близкий: форма своя
    fs = [('prop',), ('phi',), ('pos',), ('top',), ('chain',), ('nines',), ('newplace',)]
    sh = {h: mk(0.08, -1.0, fs[i], [2.0]) for i, h in enumerate(H)}
    r2 = synth(sh, 2500, 900, 3, 12)
    check('форма разная: форма своя (p ≤ 0,01)', r2['shape']['p'] <= 0.01 and r2['shape']['D'] > 0, f"D {r2['shape']['D']:.4f}, p {r2['shape']['p']:.4f}")
    # 3) все одинаковы: ни программа, ни форма не своя
    same = {h: mk(0.08, -1.2, ['prop'], [1.0]) for h in H}
    r3 = synth(same, 2500, 900, 3, 13)
    check('все одинаковы: программа не своя (p > 0,05)', r3['prog']['p'] > 0.05, f"D {r3['prog']['D']:.5f}, p {r3['prog']['p']:.4f}")
    check('все одинаковы: форма не своя (p > 0,05)', r3['shape']['p'] > 0.05, f"D {r3['shape']['D']:.5f}, p {r3['shape']['p']:.4f}")
    check('вклад входа у формы с наклоном > 0', r['input_gain']['mean'] > 0, f"{r['input_gain']['mean']:.4f}")


if __name__ == '__main__':
    t_perm()
    t_s_table()
    t_intercept()
    t_rows_match_fit_program()
    t_large_slopes()
    t_loader_keeps_phases()
    t_end_to_end()
    print('провалов:', len(FAILS), FAILS)
    sys.exit(1 if FAILS else 0)
