#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-03: тесты ab.py на заглушках с известным знаком (ворота CLAUDE.md: направленные слова, мутанты до прогона).
  python3 test_ab.py   — печатает ✓/✗ и «провалов: N»"""
import itertools
import json
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
    so = rng.normal(0, 0.1, (k, k))                                          # одна голова-выброс (как OLMo в пилоте), остальные шесть
    so[1, 1] += 2.3                                                          # взаимозаменяемы: перебор её одну не принимает за «своё»
    so[1, [0, 2, 3, 4, 5, 6]] -= 1.0
    so[[0, 2, 3, 4, 5, 6], 1] -= 1.0
    ro = ab.perm_test(so)
    check('одна голова-выброс при взаимозаменяемых остальных: p > 0,0025 (около 360/5040)', ro['p'] > 0.0025, f"D {ro['D']:.4f}, p {ro['p']:.4f}")
    ps = [ab.perm_test(rng.normal(0, 1, (k, k)))['p'] for _ in range(400)]  # нуль: p равномерно (с шагом 1/5040)
    check('нуль: доля p ≤ 0,05 около 0,05', abs(np.mean(np.array(ps) <= 0.05) - 0.05) < 0.035, f"{np.mean(np.array(ps) <= 0.05):.3f}")
    check('нуль: среднее p около 0,5', abs(np.mean(ps) - 0.5) < 0.06, f"{np.mean(ps):.3f}")


def t_trace_identity():
    """Записка литературы, §3 п. 2: D = след(M)/(k − 1) − T/(k(k − 1)), T — сумма матрицы; T от перестановки строк не зависит."""
    rng = np.random.default_rng(5)
    k = 7
    M = rng.normal(0, 1, (k, k)) + rng.normal(0, 1, k)[:, None] + rng.normal(0, 1, k)[None, :]
    D = ab.perm_test(ab.s_table([M]))['D']
    alt = np.trace(M) / (k - 1) - M.sum() / (k * (k - 1))
    check('D = след/(k − 1) − сумма/(k(k − 1))', abs(D - alt) < 1e-12, f'{D:.6f} против {alt:.6f}')
    r = ab.perm_test(ab.s_table([M]))
    check('число различных D_π записано', 1 <= r['n_distinct'] <= 5040, str(r['n_distinct']))


def t_verdicts():
    fams = {'thousands': {'prog': dict(D=0.5, p=12 / 5040, rank=12, n_perm=5040, heads_in_test=list('abcdefg')),
                          'shape': dict(D=0.1, p=13 / 5040, rank=13, n_perm=5040, heads_in_test=list('abcdefg'))},
            'length': {'prog': dict(D=-0.1, p=1 / 5040, rank=1, n_perm=5040, heads_in_test=list('abcdefg'))}}
    v = ab.verdicts(fams)
    check('вердикт: p = 12/5040 ≤ 0,0025 и D > 0 — «да»', v['АБ-П-Т']['verdict'] == 'да')
    check('вердикт: p = 13/5040 > 0,0025 — «нет»', v['АБ-Ф-Т']['verdict'] == 'нет')
    check('вердикт: D ≤ 0 — «нет» при любом p', v['АБ-П-Л']['verdict'] == 'нет')
    check('вердикт: семейства нет в выводе — None', ab.verdicts({'thousands': fams['thousands']})['АБ-Ф-Л']['verdict'] is None)
    k5 = {'thousands': {'prog': dict(D=0.9, p=1 / 120, rank=1, n_perm=120, k=5, heads_in_test=list('abcde'))}, 'length': {'k': 1, 'empty': True}}
    v5 = ab.verdicts(k5)
    check('вердикт: k = 5 (наименьшее p 1/120 > 0,0025) — «непроверяемо», а не «нет» (совет 76)', v5['АБ-П-Т']['verdict'] == 'непроверяемо',
          f"min_p {v5['АБ-П-Т']['min_p']:.4f}")
    check('вердикт: семейство без полных голов и сред — «непроверяемо»', v5['АБ-П-Л']['verdict'] == 'непроверяемо')
    k6 = {'thousands': {'prog': dict(D=0.9, p=1 / 720, rank=1, n_perm=720, k=6, heads_in_test=list('abcdef')),
                        'shape': dict(D=0.9, p=2 / 720, rank=2, n_perm=720, k=6, heads_in_test=list('abcdef'))}}
    v6 = ab.verdicts(k6)
    check('вердикт: k = 6 — «да» только при ранге 1 из 720', v6['АБ-П-Т']['verdict'] == 'да' and v6['АБ-Ф-Т']['verdict'] == 'нет')


def t_check_fits():
    ok7 = {'families': {f: {'same_as_distill02': {f'h{i}': dict(features=True, w_round=True, eps=True, q=True) for i in range(7)}}
                        for f in ('thousands', 'length')}}
    check('замок (а): 7 голов, всё совпало — проходит', ab.check_fits(ok7) == [])
    check('замок (а): пустой словарь сверки — СТОП', ab.check_fits({'families': {'thousands': {'same_as_distill02': {}}, 'length': {'same_as_distill02': {}}}}) != [])
    check('замок (а): нет семейств — СТОП', ab.check_fits({}) != [] and ab.check_fits({'families': {}}) != [])
    six = json.loads(json.dumps(ok7))
    six['families']['length']['same_as_distill02'].pop('h6')
    check('замок (а): 6 голов в семействе — СТОП', ab.check_fits(six) != [])
    bad = json.loads(json.dumps(ok7))
    bad['families']['thousands']['same_as_distill02']['h3']['eps'] = False
    none = json.loads(json.dumps(ok7))
    none['families']['thousands']['same_as_distill02']['h0'] = None
    check('замок (а): одно расхождение или None (нет формул DISTILL-02) — СТОП', ab.check_fits(bad) != [] and ab.check_fits(none) != [])


def t_s_table():
    M1 = np.array([[1.0, 0.0], [0.0, 1.0]])
    M2 = np.array([[3.0, 2.0], [1.0, 0.0]])
    s = ab.s_table([M1, M2])
    # s[a, b] = L − (S − L)/(k − 1): среда 1 — [[1, −1], [−1, 1]]; среда 2 — [[2, 2], [−2, −2]]; среднее — [[1,5, 0,5], [−1,5, −0,5]]
    check('s_table: среднее по средам', np.allclose(s, [[1.5, 0.5], [-1.5, -0.5]]), str(s.tolist()))
    try:
        ab.s_table([M1, np.array([[3.0, np.nan], [1.0, np.nan]])])
        ok = False
    except AssertionError:
        ok = True
    check('замок (г): NaN в матрице до s_table — СТОП, тихого nansum нет', ok)


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
    # разбивка: «всё» = форма + уровень + прочие у каждой головы; среднее «всего» = D программы; у «уровня разного» форма ≈ 0
    for name, res in (('уровень разный', r), ('форма разная', r2)):
        dc = res['decomposition']
        err = max(abs(dc['total']['per_head'][h] - dc['form']['per_head'][h] - dc['level']['per_head'][h] - dc['others']['per_head'][h]) for h in H)
        check(f'разбивка ({name}): всё = форма + уровень + прочие', err < 1e-9, f'{err:.1e}')
        check(f'разбивка ({name}): среднее «всего» = D программы', abs(dc['total']['mean'] - res['prog']['D']) < 1e-9)
        cd = max(abs(np.array(e['carry'])[i, i] - np.array(e['prog'])[i, i]) for e in res['envs'].values() for i in range(7))
        check(f'перенос A при «прочих» A = своя программа ({name})', cd < 1e-12, f'{cd:.1e}')
    dc = r['decomposition']
    check('уровень разный, форма одна: доля формы в преимуществе мала (< 0,2 всего)', abs(dc['form']['mean']) < 0.2 * dc['total']['mean'],
          f"форма {dc['form']['mean']:.4f}, уровень {dc['level']['mean']:.4f}, прочие {dc['others']['mean']:.4f}, всё {dc['total']['mean']:.4f}")
    dc2 = r2['decomposition']
    # ERRORS № 225: я ждал «форма — больше половины всего»; вышло форма 0,253, уровень 0,856. Порядок разбивки: «уровень» включает
    # подгонку свободного члена чужой формы к частоте ошибок B, даже когда свободные члены голов равны. Проверяю то, что верно по устройству.
    check('форма разная, уровень и прочие одни: «прочие» ≈ 0 (ε и q у голов одни)', abs(dc2['others']['mean']) < 0.01,
          f"форма {dc2['form']['mean']:.4f}, уровень {dc2['level']['mean']:.4f}, прочие {dc2['others']['mean']:.4f}, всё {dc2['total']['mean']:.4f}")
    check('форма разная, свободные члены равны: «уровень» > 0 — подгонка чужой формы (свойство порядка разбивки)', dc2['level']['mean'] > 0,
          f"уровень {dc2['level']['mean']:.4f}")


REAL = ['Falcon3-1B-Instruct', 'OLMo-2-0425-1B-Instruct', 'Qwen2.5-0.5B-Instruct', 'Qwen2.5-1.5B-Instruct', 'SmolLM2-1.7B-Instruct',
        'SmolLM2-360M-Instruct', 'TinyLlama-1.1B-Chat-v1.0']


def direct_D_p(Ls):
    """Прямой счёт D и точного p — отдельно от s_table и perm_test (совет 76, инженер): циклы по перестановкам, головам и средам.
    Ls — матрицы сред (строки — чья программа, столбцы — чьи ответы); D_π = среднее по B от среднего по средам
    [L(π(B), B) − среднее по A ≠ π(B) от L(A, B)]."""
    k = len(Ls[0])

    def D_of(perm):
        tot = 0.0
        for b in range(k):
            a = perm[b]
            acc = 0.0
            for L in Ls:
                acc += L[a][b] - sum(L[x][b] for x in range(k) if x != a) / (k - 1)
            tot += acc / len(Ls)
        return tot / k
    D = D_of(tuple(range(k)))
    vals = [D_of(pm) for pm in itertools.permutations(range(k))]
    return D, sum(v >= D - 1e-12 for v in vals) / len(vals), len(vals)


def t_complete_case():
    """Совет 76, п. 4: голова без данных — выкинута целиком (k × k, перебор k!); голова без данных в одной среде — среда выкинута у всех;
    k = 5 — «непроверяемо». Сверка с прямым счётом до 1e-12."""
    H = [f'h{i}' for i in range(7)]
    fs = [('prop',), ('chain',), ('pos',), ('top',), ('nines',), ('newplace',), ('phi',)]
    progs = {h: mk(0.03 + 0.02 * i, -1.5 + 0.2 * i, fs[i], [1.5]) for i, h in enumerate(H)}
    rng = np.random.default_rng(16)
    con = items_pool(1500, rng)
    P = ab.programs_from(con, {h: np.array([D2.sample_program(p, it, rng) for it in con]) for h, p in progs.items()})

    def env(n, absent=()):
        it = items_pool(n, rng)
        return (it, {h: (np.full(n, D2.NC) if h in absent else np.array([D2.sample_program(p, x, rng) for x in it])) for h, p in progs.items()})
    envs = {f'E{i}': env(260, absent=('h6',)) for i in range(3)}
    r = ab.family_result(P, envs, sorted(envs), H)
    raw = [ab.matrices_from(P, *envs[n], H)[0] for n in sorted(envs)]
    for kind in ab.KINDS:
        D, p, n = direct_D_p([[[M[kind][a][b] for b in range(6)] for a in range(6)] for M in raw])
        check(f'голова без данных ({kind}): k = 6, перебор 720, D и p — как прямой счёт на 6 × 6 (1e-12)',
              r[kind]['k'] == 6 and r[kind]['n_perm'] == 720 == n and abs(r[kind]['D'] - D) < 1e-12 and abs(r[kind]['p'] - p) < 1e-12,
              f"D {r[kind]['D']:.6f} / {D:.6f}, p {r[kind]['p']:.5f} / {p:.5f}")
    check('голова без данных: выкинута и как программа, и как ответы', r['heads_dropped'] == ['h6'] and r['heads_kept'] == H[:6] and r['envs_dropped'] == [])
    envs2 = {'E0': env(260), 'E1': env(260, absent=('h2',)), 'E2': env(260)}
    r2 = ab.family_result(P, envs2, sorted(envs2), H)
    raw2 = {n: ab.matrices_from(P, *envs2[n], H)[0] for n in envs2}
    for kind in ab.KINDS:
        D, p, n = direct_D_p([[[raw2[e][kind][a][b] for b in range(7)] for a in range(7)] for e in ('E0', 'E2')])
        check(f'голова без данных в одной среде ({kind}): среда выкинута у всех голов, D и p — как прямой счёт без неё (1e-12)',
              r2['envs_dropped'] == ['E1'] and r2['heads_dropped'] == [] and r2[kind]['k'] == 7 and abs(r2[kind]['D'] - D) < 1e-12
              and abs(r2[kind]['p'] - p) < 1e-12, f"D {r2[kind]['D']:.6f} / {D:.6f}, p {r2[kind]['p']:.5f} / {p:.5f}")
    envs3 = {f'E{i}': env(260, absent=('h5', 'h6')) for i in range(2)}
    r3 = ab.family_result(P, envs3, sorted(envs3), H)
    v3 = ab.verdicts({'thousands': r3, 'length': r3})
    check('k = 5 (две головы без данных): все четыре вердикта «непроверяемо»', all(x['verdict'] == 'непроверяемо' for x in v3.values()),
          str({k: (x['verdict'], x.get('k'), round(x.get('min_p'), 4)) for k, x in v3.items()}))


def t_kinship():
    """Родичи с одной программой: своя ≈ родич; родич лучше чужих. Головы названы как настоящие (пары KIN)."""
    fs = {'Falcon3-1B-Instruct': ('top',), 'OLMo-2-0425-1B-Instruct': ('chain',), 'TinyLlama-1.1B-Chat-v1.0': ('nines',),
          'Qwen2.5-0.5B-Instruct': ('prop',), 'Qwen2.5-1.5B-Instruct': ('prop',), 'SmolLM2-360M-Instruct': ('pos',), 'SmolLM2-1.7B-Instruct': ('pos',)}
    progs = {h: mk(0.08, -1.0, f, [2.0]) for h, f in fs.items()}
    r = synth(progs, 2500, 900, 3, 14)
    kp = r['kinship']['shape']
    worst_rel = max(abs(v['own_minus_relative']) for v in kp['per_head'].values())
    check('родство: у родичей с одной программой своя ≈ родич (|разница| < 0,02)', worst_rel < 0.02, f'{worst_rel:.4f}')
    check('родство: родич лучше чужих у всех четырёх голов', len(kp['per_head']) == 4 and all(v['relative_minus_strangers'] > 0 for v in kp['per_head'].values()),
          str({h: round(v['relative_minus_strangers'], 4) for h, v in kp['per_head'].items()}))


def t_run_cmd_dry():
    """Сухой прогон всей цепочки `ab.py test` на заглушках: сборка из папок, замки, вердикты, описательный набор."""
    import json as _json
    import tempfile
    rng = np.random.default_rng(15)
    fs = [('prop',), ('chain',), ('pos',), ('top',), ('nines',), ('newplace',), ('phi',)]
    progs = {h: mk(0.03 + 0.02 * i, -1.5 + 0.2 * i, fs[i], [1.5]) for i, h in enumerate(REAL)}

    def env(n):
        it = items_pool(n, rng)
        return dict(items=it, offs={h: np.array([D2.sample_program(p, x, rng) for x in it]) for h, p in progs.items()})
    dirs = {'c_T': {'T_X19_p3': env(700), 'T_X29_p3': env(700)}, 'c_L': {'L_X9_p3': env(700), 'L_X99_p3': env(700)},
            't_T': {n: env(260) for n in ('T_X19_p3',) + ab.TEST_ENVS['thousands']}, 't_L': {n: env(260) for n in ab.TEST_ENVS['length']},
            'n_T': {'T_X109_p3': env(260)}, 'dup': {'T_X29_p3': env(260)}}
    orig = (D2.load_merged, D2.env_table)
    try:
        D2.load_merged = lambda d: dirs[d]
        D2.env_table = lambda e, heads=None, with_logp=False: (e['items'], e['offs'])
        spec = {'construction': {'thousands': ['c_T'], 'length': ['c_L']}, 'test': {'thousands': ['t_T'], 'length': ['t_L']},
                'descriptive': {'thousands': {'new5': ['n_T']}}}
        tmp = tempfile.mkdtemp()
        rc = ab.run_cmd(os.path.join(tmp, 'test.json'), spec, 'test')
        out = _json.load(open(os.path.join(tmp, 'test.json'), encoding='utf-8'))
        v = out['verdicts']
        check('сухой прогон: четыре вердикта, у всех семь голов', rc == 0 and len(v) == 4 and all(x['heads'] == 7 for x in v.values()),
              str({k: (x['verdict'], round(x['D'], 3), x['p']) for k, x in v.items()}))
        check('сухой прогон: формы разные — все четыре «да»', all(x['verdict'] == 'да' for x in v.values()))
        check('сухой прогон: в тесте ровно среды TEST_ENVS (пилот T_X19 не вошёл)',
              sorted(out['families']['thousands']['envs']) == sorted(ab.TEST_ENVS['thousands']) and
              sorted(out['families']['length']['envs']) == sorted(ab.TEST_ENVS['length']))
        check('сухой прогон: описательный набор new5 посчитан', list(out['families']['thousands'].get('descriptive', {})) == ['new5'])
        fam = out['families']['thousands']
        j = fam['heads'].index('OLMo-2-0425-1B-Instruct')
        rest = [x for x in range(7) if x != j]
        for kind in ab.KINDS:
            D, p, n = direct_D_p([[[fam['envs'][e][kind][a][b] for b in rest] for a in rest] for e in fam['envs_kept']])
            w = fam[kind]['without']['OLMo-2-0425-1B-Instruct']
            check(f'сухой прогон: без OLMo ({kind}, описательно) — k = 6, перебор 720, D и p как прямой счёт (1e-12)',
                  w['k'] == 6 and w['n_perm'] == 720 == n and abs(w['D'] - D) < 1e-12 and abs(w['p'] - p) < 1e-12, f"D {w['D']:.5f}, p {w['p']:.5f}")
        check('сухой прогон: в выводе k и наименьшее p у каждого вердикта', all(x['k'] == 7 and abs(x['min_p'] - 1 / 5040) < 1e-15 for x in v.values()))
        check('сухой прогон: хеши кода записаны', set(out['code']) == {'ab.py', 'distill02.py'} and all(len(x) == 64 for x in out['code'].values()))
        bad = dict(spec, test={'thousands': ['t_T'], 'length': ['n_T']})
        try:
            ab.run_cmd(os.path.join(tmp, 'bad.json'), bad, 'test')
            ok = False
        except AssertionError as e:
            ok = 'нет сред' in str(e)
        check('замок: в тесте нет сред семейства — СТОП', ok)
        dup = dict(spec, test={'thousands': ['t_T', 'dup'], 'length': ['t_L']})
        try:
            ab.run_cmd(os.path.join(tmp, 'dup.json'), dup, 'test')
            ok = False
        except AssertionError as e:
            ok = 'дважды' in str(e)
        check('замок: одна среда теста дважды — СТОП', ok)
    finally:
        D2.load_merged, D2.env_table = orig


if __name__ == '__main__':
    t_perm()
    t_trace_identity()
    t_verdicts()
    t_check_fits()
    t_s_table()
    t_intercept()
    t_rows_match_fit_program()
    t_large_slopes()
    t_loader_keeps_phases()
    t_end_to_end()
    t_kinship()
    t_complete_case()
    t_run_cmd_dry()
    print('провалов:', len(FAILS), FAILS)
    sys.exit(1 if FAILS else 0)
