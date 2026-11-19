#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04: тесты разведки на заглушках с известным ответом (операторы, классы ответов, покрытие).
  python3 test_explore_d4.py   — печатает ✓/✗ и «провалов: N»"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_d4 as X  # noqa: E402

FAILS = []


def check(name, cond, info=''):
    print(('✓ ' if cond else '✗ ') + name + (f' — {info}' if info else ''), flush=True)
    if not cond:
        FAILS.append(name)


def it(a, b):
    return dict(a=a, b=b, sum=a + b, ood=0)


def t_candidates():
    c = X.candidates(1957, 86)                       # s = 2043; переносы в разряды 1, 2, 3
    check('переносы 1957 + 86 — разряды 1, 2, 3', X.carry_positions(1957, 86) == [1, 2, 3], str(X.carry_positions(1957, 86)))
    check('plus10j', c['plus10j'] == {2044, 2053, 2143, 3043, 12043}, str(sorted(c['plus10j'])))
    check('minus10j — только разряд без переноса', c['minus10j'] == {2042}, str(sorted(c['minus10j'])))
    check('shift', c['shift'] == {2817, 1965, 19656, 281}, str(sorted(c['shift'])))
    check('operand', c['operand'] == {1957, 86})
    check('omit_digit', c['omit_digit'] == {43, 243, 203, 204}, str(sorted(c['omit_digit'])))
    check('dup_digit', c['dup_digit'] == {22043, 20043, 20443, 20433}, str(sorted(c['dup_digit'])))
    check('transpose — без ведущего нуля', c['transpose'] == {2403, 2034}, str(sorted(c['transpose'])))
    check('concat', c['concat'] == {195786, 861957})
    check('верной суммы нет ни в одном операторе', all(2043 not in v for v in c.values()))


def t_classify():
    x = it(1957, 86)
    check('d = 0 — верно', X.classify(x, 0) == 'correct')
    check('d = −10 (потерян перенос в разряд 1) — потеря переноса', X.classify(x, -10) == 'lost')
    check('d = −110 (потеряны переносы 1 и 2) — потеря переноса', X.classify(x, -110) == 'lost')
    check('d = −1 (разряд 0 без переноса) — «прочее»', X.classify(x, -1) == 'other')
    check('d = +10 — «прочее»', X.classify(x, 10) == 'other')
    check('нечисловой — None', X.classify(x, X.NC) is None)


def t_head_stats():
    items = [it(1957, 86)] * 6
    offs = [0, -10, -1, 2817 - 2043, 7 - 2043, X.NC]           # верно, потеря, minus10j, shift, необъяснённое (7), нечисловой
    st = X.head_stats(items, offs, table={-1})
    check('классы: 5 числовых, 1 верный, 1 потеря, 3 «прочих»', (st['numeric'], st['correct'], st['lost'], st['other']) == (5, 1, 1, 3), str(st))
    check('операторы объясняют 2 из 3 «прочих»', st['union']['n'] == 2 and abs(st['union']['share'] - 2 / 3) < 1e-12)
    check('minus10j 1, shift 1', st['by_op']['minus10j']['n'] == 1 and st['by_op']['shift']['n'] == 1)
    check('необъяснённое смещение −2036 в списке', st['unexplained_top'] == [(7 - 2043, 1)], str(st['unexplained_top']))
    check('таблица {−1} покрывает 1 из 3', st['table']['n'] == 1)


if __name__ == '__main__':
    t_candidates()
    t_classify()
    t_head_stats()
    print('провалов:', len(FAILS), FAILS)
    sys.exit(1 if FAILS else 0)
