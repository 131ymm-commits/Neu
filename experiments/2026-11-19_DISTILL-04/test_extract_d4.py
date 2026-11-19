#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04: замки свежести задач теста (до извлечения, без моделей): новые X не встречались ни в одной прежней фазе, задачи test6L
не пересекаются с прежними задачами L_X9999 (OCDIV-02 и new5 DISTILL-02), размеры сред — 2200.
  python3 test_extract_d4.py   — печатает ✓/✗ и «провалов: N»"""
import os
import sys

X_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X_DIR))
sys.path.insert(0, X_DIR)
sys.path.insert(0, os.path.join(ROOT, 'experiments/2026-11-18_DISTILL-02'))
import distill04_extract as X4  # noqa: E402
import distill02_extract as XD  # noqa: E402

X2 = X4.X2
FAILS = []


def check(name, cond, info=''):
    print(('✓ ' if cond else '✗ ') + name + (f' — {info}' if info else ''), flush=True)
    if not cond:
        FAILS.append(name)


def pairs_of(e):
    return set((q['a'], q['b']) for q in e['problems'])


def main():
    t6 = X4.envs_d4('test6')
    names = [e['name'] for e in t6]
    check('test6: восемь сред T_X14_p3 … T_X84_p3', names == [f'T_X{x}_p3' for x in (14, 24, 34, 44, 54, 64, 74, 84)], str(names))
    check('test6: в каждой среде 2200 задач', all(len(e['problems']) == 2200 for e in t6))
    check('test6: ни одного X из прежних фаз', not set(X4.FAMILIES6['test6']['thousands']) & set(X4.USED_THOUSANDS_X))
    used_ranges = [(100 * x, 100 * x + 99) for x in X4.USED_THOUSANDS_X]
    a_new = set(q['a'] for e in t6 for q in e['problems'])
    check('test6: ни одно a не лежит в прежних диапазонах a', not any(lo <= a <= hi for a in a_new for lo, hi in used_ranges))
    used_x_in_code = set(XD.FAMILIES5['test5']['thousands']) | set(XD.FAMILIES5['new5']['thousands']) | set(X2.FAMILIES['thousands']['X'])
    check('прежние X в коде DISTILL-02 и OCDIV-02 — внутри списка USED_THOUSANDS_X', used_x_in_code <= set(X4.USED_THOUSANDS_X), str(sorted(used_x_in_code)))
    l6 = X4.envs_d4('test6L')
    check('test6L: одна среда L_X9999_p3, 2200 задач', [e['name'] for e in l6] == ['L_X9999_p3'] and len(l6[0]['problems']) == 2200)
    new5 = [e for e in XD.envs_d2('new5') if e['name'] == 'L_X9999_p3'][0]
    prev = [pairs_of(new5)]
    if 9999 in X2.FAMILIES.get('length', {}).get('X', ()):
        for ph in X2.PHASES:
            prev += [pairs_of(e) for e in X2.envs_ocdiv2(ph, ('length',)) if e['name'].startswith('L_X9999')]
    ov = [len(pairs_of(l6[0]) & p) for p in prev]
    check('test6L: задачи не пересекаются с прежними фазами L_X9999', all(x == 0 for x in ov), f'пересечений по фазам: {ov}; фаз сверено: {len(prev)}')
    check('test6L: места после new5', l6[0]['place'][0] >= new5['place'][1], f"{l6[0]['place']} против new5 {new5['place']}")
    print('провалов:', len(FAILS), FAILS)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
