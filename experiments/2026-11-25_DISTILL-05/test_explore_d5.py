#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-05: проверки разведки на заглушках (масштаб смещения, места кусков, подсчёт по длине суммы).
  python3 test_explore_d5.py   — печатает ✓/✗ и «провалов: N»"""
import json
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_d5 as X  # noqa: E402

FAILS = []


def check(name, cond, info=''):
    print(('✓ ' if cond else '✗ ') + name + (f' — {info}' if info else ''), flush=True)
    if not cond:
        FAILS.append(name)


def main():
    check('масштаб: −20 → 1, −300 → 2, 7 → 0, −1010 → 1', [X.scale(d) for d in (-20, -300, 7, -1010)] == [1, 2, 0, 1])
    check('куски по три слева направо: 4 цифры → [1, 0], 5 → [2, 0], 6 → [3, 0], 7 → [4, 1, 0]',
          [X.chunk_places(n) for n in (4, 5, 6, 7)] == [[1, 0], [2, 0], [3, 0], [4, 1, 0]], str([X.chunk_places(n) for n in (4, 5, 6, 7)]))
    items = [dict(a=1957, b=86, sum=2043, ood=1), dict(a=10957, b=86, sum=11043, ood=1), dict(a=1957, b=86, sum=2043, ood=1)]
    env = dict(items=items, offs={'h': np.array([-20, -200, 0])})
    orig = (X.D2.load_merged, X.D2.env_table)
    try:
        X.D2.load_merged = lambda d: {'E': env}
        X.D2.env_table = lambda e, heads=None, with_logp=False: (e['items'], e['offs'])
        tmp = tempfile.mkdtemp()
        json.dump({'sets': {'s': ['x']}}, open(os.path.join(tmp, 'spec.json'), 'w'))
        X.main([os.path.join(tmp, 'o.json'), os.path.join(tmp, 'spec.json')])
        o = json.load(open(os.path.join(tmp, 'o.json')))['heads']['h']
    finally:
        X.D2.load_merged, X.D2.env_table = orig
    check('подсчёт по длине суммы: n = 4 — одно «прочее» −20 масштаба 1 и один верный; n = 5 — «прочее» −200 масштаба 2',
          o['4']['n_other'] == 1 and o['4']['n_numeric'] == 2 and o['4']['scales'] == {'1': 1.0} and o['5']['scales'] == {'2': 1.0},
          str({n: (v['n_numeric'], v['n_other'], v['scales']) for n, v in o.items()}))
    print('провалов:', len(FAILS), FAILS)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
