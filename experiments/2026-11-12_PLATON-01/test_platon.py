#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-01: модульные тесты мира и проверщика; второй способ проверки правды (до прогона).

1. Правда вторым способом: невязка каждого закона пересчитана формулой, записанной здесь заново (не из platon_world.LAWS),
   по параметрам экземпляра: на показанных строках T — в пределах ошибки округления, на новых строках — машинная точность;
   на Z истинный закон не держится (R ≥ 0,3).
2. Проверщик: равносильные формы держатся и согласуются; знакомые, но неверные формы не держатся; в Z одинаковые и
   равносильно переписанные ложные утверждения согласуются, разные — нет; тривиальные, одностолбцовые, неразборные.
3. Нормализация записи ответов.
Запуск: python3 test_platon.py [число зёрен на закон, по умолчанию 3] — печатает итог, код 1 при провале.
"""
import math
import sys

import numpy as np

import platon_world as W
import platon_check as C

FAIL = []


def check(cond, msg):
    if not cond:
        FAIL.append(msg)
        print('  ✗', msg)


# ---------- 1. правда вторым способом ----------
def residual(law, p, x):
    """Невязка закона, записанная заново (относительная)."""
    if law == 'fall':
        return x['h'] / (0.5 * p['g'] * x['t'] * x['t']) - 1
    if law == 'pendulum':
        return x['T'] * x['T'] * p['g'] / (4 * math.pi * math.pi * x['L']) - 1
    if law == 'kepler':
        return x['T'] * x['T'] * p['M'] / x['a'] ** 3 - 1
    if law == 'gas':
        return x['P'] * x['V'] / (p['nR'] * x['T']) - 1
    if law == 'lens':
        return (1 / x['d1'] + 1 / x['d2']) * p['f'] - 1
    if law == 'spring':
        return (x['x'] ** 2 + (x['v'] / p['w']) ** 2) / p['A'] ** 2 - 1
    if law == 'energy':
        return (0.5 * x['v'] ** 2 + 9.81 * x['h']) / (9.81 * p['H']) - 1
    if law == 'coulomb':
        return x['F'] * x['r'] ** 2 * p['eps'] / (8.99e-3 * x['q1'] * x['q2']) - 1
    if law == 'ohm':
        return x['U'] / (x['I'] * x['R']) - 1
    if law == 'kinetic':
        return 2 * x['E'] / (x['m'] * x['v'] ** 2) - 1
    raise KeyError(law)


# Равносильные формы (держатся и согласуются с канонической) и неверные знакомые формы (не держатся).
def forms(law, p):
    w2 = p.get('w', 1) ** 2
    eq = {
        'fall': lambda: ['h/t**2', 't**2/h', 'sqrt(h)/t', 'log(h) - 2*log(t)', f"h - {p['g'] / 2!r}*t**2"],
        'pendulum': lambda: ['T**2/L', 'T/sqrt(L)', 'L/T**2', f"T - {2 * math.pi / math.sqrt(p['g'])!r}*sqrt(L)"],
        'kepler': lambda: ['T**2/a**3', 'T/a**1.5', 'a**3/T**2', '2*log(T) - 3*log(a)'],
        'gas': lambda: ['P*V/T', 'T/(P*V)', 'log(P) + log(V) - log(T)', f"P*V - {p['nR']!r}*T"],
        'lens': lambda: ['1/d1 + 1/d2', 'd1*d2/(d1 + d2)', '(d1 + d2)/(d1*d2)'],
        'spring': lambda: [f'x**2 + v**2/{w2!r}', f'{w2!r}*x**2 + v**2', f'sqrt(x**2 + v**2/{w2!r})'],
        'energy': lambda: ['v**2/2 + 9.81*h', 'v**2 + 19.62*h', '0.5*v**2 + 9.8*h', 'v**2/19.62 + h'],
        'coulomb': lambda: ['F*r**2/(q1*q2)', 'q1*q2/(F*r**2)', 'sqrt(F)*r/sqrt(q1*q2)'],
        'ohm': lambda: ['U/(I*R)', 'U - I*R', 'I*R/U', 'log(U) - log(I) - log(R)'],
        'kinetic': lambda: ['E/(m*v**2)', '2*E/(m*v**2)', 'sqrt(2*E/m)/v', 'E - m*v**2/2'],
    }[law]()
    wrong = {
        'fall': ['h/t', 'h*t', 'h/t**3'],
        'pendulum': ['T/L', 'T*L', 'T**2*L'],
        'kepler': ['T/a', 'T**2/a**2', 'T*a'],
        'gas': ['P*V', 'P/T', 'V/T', 'P*T/V'],
        'lens': ['d1 + d2', 'd1*d2', 'd1/d2'],
        'spring': ['x**2 + v**2', 'x*v', 'x/v'] if abs(w2 - 1) > 0.5 else ['x*v', 'x/v'],
        'energy': ['v**2 + 9.81*h', 'v*h', 'v + h', 'v**2/2 - 9.81*h'],
        'coulomb': ['F*r/(q1*q2)', 'F*r**2', 'F*r**2/q1'],
        'ohm': ['U/I', 'U/R', 'U*I*R'],
        'kinetic': ['E/(m*v)', 'E/m', 'E/v**2'],
    }[law]
    return eq, wrong


# Номера форм из eq, которые — функции канонической формы (согласуются и в Z при любой медиане).
FUNC_EQ = {'fall': {0, 1, 2, 3}, 'pendulum': {0, 1, 2}, 'kepler': {0, 1, 2, 3}, 'gas': {0, 1, 2}, 'lens': {0, 1, 2},
           'spring': {0, 1, 2}, 'energy': {0, 1, 3}, 'coulomb': {0, 1, 2}, 'ohm': {0, 2, 3}, 'kinetic': {0, 1, 2}}


def test_law(law, seed):
    inst = W.make_instance(seed, law)
    p = inst['params']; cols = inst['cols']
    # 1. правда вторым способом
    rT = [abs(residual(law, p, x)) for x in inst['shown']['T']]
    check(max(rT) < 0.02, f'{law}/{seed}: невязка показанных строк T {max(rT):.4f} ≥ 0,02')
    for part in ('in', 'out'):
        rh = [abs(residual(law, p, x)) for x in inst['hold']['T'][part]]
        check(max(rh) < 1e-9, f'{law}/{seed}: невязка новых строк T/{part} {max(rh):.2e}')
    for part in ('in', 'out'):
        free = [x[k] for x in inst['hold']['T'][part] for k in W.LAWS[law]['free']]
        check(all(v > 0 for v in free), f'{law}/{seed}: неположительные значения в новых строках {part}')
    # диапазон out действительно вне показанного (хотя бы по одной свободной переменной)
    rng = p['rng']
    outside = [any(not (rng[k][0] <= x[k] <= rng[k][1]) for k in W.LAWS[law]['free']) for x in inst['hold']['T']['out']]
    check(all(outside), f'{law}/{seed}: строки out внутри показанного диапазона')
    rZ = [abs(residual(law, p, x)) for x in inst['shown']['Z']]
    # связь в Z разрушена: типичная невязка в Z много больше ошибки округления показанных строк T
    check(np.median(rZ) > 5 * max(rT), f'{law}/{seed}: в Z медиана невязки {np.median(rZ):.4f} ≤ 5 × макс. невязки T {max(rT):.4f}')
    stats = {}
    approx_T = {}
    for names in ('S', 'N'):
        mp = {c: c for c in cols} if names == 'S' else inst['letters']
        idents = [mp[c] for c in inst['order']]
        ren = lambda e: W.re_names(e, mp) if hasattr(W, 're_names') else _ren(e, mp)
        for data in ('T', 'Z'):
            shown = W.rename_rows(inst['shown'][data], mp)
            hin = W.rename_rows(inst['hold'][data]['in'], mp)
            hout = W.rename_rows(inst['hold'][data]['out'], mp)
            eq, wrong = forms(law, p)
            claims = []
            for k, e in enumerate(eq):
                cl = C.Claim(ren(e), idents, shown, f'eq|{law}|{seed}|{names}|{data}|{k}')
                check(cl.valid, f'{law}/{seed}/{names}{data}: форма «{e}» не годна ({cl.kind} {cl.err})')
                if not cl.valid:
                    continue
                h = C.holds(cl, hin, hout, f'{law}|{seed}|{names}|{data}|eq{k}')
                Rs = C.R_measure(cl.f, shown, idents, seed=f'shown|{law}|{seed}|{k}')
                if data == 'T':
                    check(h['holds'], f'{law}/{seed}/{names}T: равносильная «{e}» не держится (R_in {h["R_in"]:.3f}, R_out {h["R_out"]:.3f})')
                    check(Rs < C.TAU, f'{law}/{seed}/{names}T: равносильная «{e}» R на показанных {Rs:.3f}')
                    stats.setdefault('R_true_shown', []).append(Rs)
                    stats.setdefault('R_true_hold', []).append(max(h['R_in'], h['R_out']))
                else:
                    check(not h['holds'], f'{law}/{seed}/{names}Z: «{e}» держится в Z')
                    check(Rs > 0.3, f'{law}/{seed}/{names}Z: «{e}» R на показанных Z {Rs:.3f} ≤ 0,3')
                    stats.setdefault('R_Z_shown', []).append(Rs)
                claims.append((e, cl))
            # все равносильные формы попарно согласуются — и в T, и в Z (в Z это одна и та же ложная связь)
            for i in range(len(claims)):
                for j in range(i + 1, len(claims)):
                    ok, r21, r12 = C.agree(claims[i][1], claims[j][1], shown, f'{law}|{seed}|{names}|{data}|{i}|{j}')
                    if data == 'T':
                        check(ok, f'{law}/{seed}/{names}T: «{claims[i][0]}» и «{claims[j][0]}» не согласованы ({r21:.3f}, {r12:.3f})')
                    else:
                        # в Z равносильность форм должна сохраниться для точных переписываний (без подогнанных констант)
                        # функции одного выражения (без подогнанных констант и без формы «разность»)
                        exact = i in FUNC_EQ[law] and j in FUNC_EQ[law]
                        if exact:
                            check(ok, f'{law}/{seed}/{names}Z: точные переписывания «{claims[i][0]}» и «{claims[j][0]}» не согласованы ({r21:.3f}, {r12:.3f})')
                    stats.setdefault('agree_eq_' + data, []).append(ok)
            # неверные знакомые формы: не держатся и не согласуются с канонической
            can = claims[0][1] if claims else None
            for k, e in enumerate(wrong):
                cl = C.Claim(ren(e), idents, shown, f'wr|{law}|{seed}|{names}|{data}|{k}')
                check(cl.valid, f'{law}/{seed}/{names}{data}: неверная форма «{e}» не годна ({cl.kind})')
                if not cl.valid:
                    continue
                h = C.holds(cl, hin, hout, f'{law}|{seed}|{names}|{data}|wr{k}')
                check(not h['holds'], f'{law}/{seed}/{names}{data}: неверная «{e}» держится (R_in {h["R_in"]:.3f})')
                Rw = C.R_measure(cl.f, shown, idents, seed=f'shownw|{law}|{seed}|{k}')
                if can is not None and data == 'T' and Rw < C.TAU:
                    # неверная форма приближённо верна в показанном диапазоне (например v + h при малой высоте):
                    # в области данных она неотличима от закона; отличает её только проверка вне диапазона
                    stats.setdefault('wrong_approx_in_range_T', []).append(1.0)
                    approx_T[(names, k)] = True
                    check(h['R_out'] >= C.TAU, f'{law}/{seed}/{names}T: неверная «{e}» держится и вне диапазона')
                elif can is not None and data == 'Z' and approx_T.get((names, k)):
                    stats.setdefault('wrong_approx_skipped_Z', []).append(1.0)   # в области данных неотличима (см. T)
                elif can is not None:
                    ok, r21, r12 = C.agree(can, cl, shown, f'{law}|{seed}|{names}|{data}|w{k}')
                    check(not ok, f'{law}/{seed}/{names}{data}: «{eq[0]}» и неверная «{e}» согласованы ({r21:.3f}, {r12:.3f})')
                    stats.setdefault('agree_wrong_' + data, []).append(ok)
    return stats


def _ren(expr, mp):
    import re
    return re.sub(r'\b[A-Za-z_][A-Za-z_0-9]*\b', lambda m: mp.get(m.group(0), m.group(0)), expr)


def test_parse():
    idents = ['v', 'h']
    shown = [{'v': 3.0 + i, 'h': 1.0 + 0.5 * i} for i in range(13)]
    cases = [
        ('НЕТ', 'NONE'), ('нет', 'NONE'), ('None', 'NONE'), ('', 'NONE'),
        ('v²/2 + 9.81·h', 'EXPR'), ('E = v^2/2 + 9.81h', 'EXPR'), ('v**2/2 + 9.81*h = const', 'EXPR'),
        ('`v*h`', 'EXPR'), ('v − h', 'EXPR'), ('√v * h', 'EXPR'), ('2v + h', 'EXPR'),
        ('v - v', 'TRIVIAL'), ('v/v + h - h', 'TRIVIAL'), ('0*v + 3', 'TRIVIAL'),
        ('v**2/2 + g*h', 'PARSE_ERR'), ('import os', 'PARSE_ERR'), ('__import__("os")', 'PARSE_ERR'),
        ('v.real', 'PARSE_ERR'), ('[v, h]', 'PARSE_ERR'), ('v if h else 1', 'PARSE_ERR'), ('log(v, 2)', 'PARSE_ERR'),
        ('sqrt(-v - h)', 'INVALID'),
    ]
    for raw, kind in cases:
        cl = C.Claim(raw, idents, shown, f'parse|{raw}')
        check(cl.kind == kind, f'разбор «{raw}»: {cl.kind} вместо {kind} ({cl.err})')
    one = C.Claim('v', idents, shown, 'parse|one')
    check(one.valid and one.deps == ['v'], f'одностолбцовое «v»: {one.kind}, {one.deps}')
    R = C.R_measure(one.f, shown, idents, seed='one')
    check(abs(R - 1) < 1e-9, f'одностолбцовое: R = {R} вместо 1')


def test_z_false_claims():
    """В Z: одинаковые ложные утверждения согласуются; разные — нет (случайные пары выражений)."""
    inst = W.make_instance(3, 'gas')
    cols = inst['cols']; idents = [c for c in inst['order']]
    shown = inst['shown']['Z']
    a = C.Claim('P*V/T', idents, shown, 'z1'); b = C.Claim('P*V/T', idents, shown, 'z2')
    ok, *_ = C.agree(a, b, shown, 'zz1'); check(ok, 'Z: одинаковые ложные утверждения не согласованы')
    c = C.Claim('T/(V*P)', idents, shown, 'z3')
    ok, *_ = C.agree(a, c, shown, 'zz2'); check(ok, 'Z: точное переписывание ложного утверждения не согласовано')
    pool = ['P*V', 'P/T', 'V/T', 'P*T/V', 'P+V', 'P*V*T', 'V*T/P', 'P - V', 'P/V', 'T - P']
    n_ok = 0; n = 0
    for i in range(len(pool)):
        for j in range(i + 1, len(pool)):
            x = C.Claim(pool[i], idents, shown, f'zp{i}'); y = C.Claim(pool[j], idents, shown, f'zq{j}')
            ok, *_ = C.agree(x, y, shown, f'zz|{i}|{j}')
            n += 1; n_ok += ok
    check(n_ok == 0, f'Z: разные ложные утверждения согласованы в {n_ok} парах из {n}')
    return n_ok, n


if __name__ == '__main__':
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    test_parse()
    nz = test_z_false_claims()
    agg = {}
    for law in W.LAW_ORDER:
        for s in range(k):
            st = test_law(law, 70000 + 100 * W.LAW_ORDER.index(law) + s)   # зёрна тестов: 70000+ (вне пилота и теста)
            for kk, v in st.items():
                agg.setdefault(kk, []).extend(v)
    print('сводка:')
    for kk in sorted(agg):
        v = np.array(agg[kk], dtype=float)
        print(f'  {kk}: n {v.size}, медиана {np.median(v):.4f}, макс {v.max():.4f}, мин {v.min():.4f}')
    print(f'  Z, разные ложные пары: согласовано {nz[0]} из {nz[1]}')
    print('ПРОВАЛОВ:', len(FAIL))
    sys.exit(1 if FAIL else 0)
