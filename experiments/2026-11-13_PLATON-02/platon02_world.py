#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-02 «мимикрия»: имена и описания знакомого закона X, данные — по сдвинутому закону Y на тех же величинах.

Код мира PLATON-01 (../2026-11-12_PLATON-01/platon_world.py) не меняется: законы-двойники добавляются в W.LAWS.
У двойника: столбцы, описания, свободные и зависимая — как у X; диапазоны и выход за диапазон — как у X;
решение и каноническое выражение 'inv' — закона Y (правда данных); 'prior' — каноническое выражение X (априор по имени).
Постоянные Y берутся из того же потока 'params' после постоянных X (детерминировано по зерну)."""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.join(HERE, '..', '2026-11-12_PLATON-01')
if P1 not in sys.path:
    sys.path.insert(0, P1)
import platon_world as W      # noqa: E402


def _wrap(xkey, extra):
    base = W.LAWS[xkey]['params']

    def params(r):
        p = base(r)
        extra(p, r)
        return p
    return params


def _mimic(xkey, extra, solve, inv):
    X = W.LAWS[xkey]
    return {'cols': X['cols'], 'free': X['free'], 'dep': X['dep'], 'params': _wrap(xkey, extra),
            'solve': solve, 'inv': inv, 'out': X['out'], 'prior': X['inv'], 'mimic_of': xkey}


MIMIC = {
    'fall_m': _mimic('fall', lambda p, r: p.update(k=r.uniform(1, 10)),
                     lambda p, x: p['k'] * x['t'], lambda p: 'h/t'),
    'pendulum_m': _mimic('pendulum', lambda p, r: p.update(k=r.uniform(1, 3)),
                         lambda p, x: p['k'] * x['L'], lambda p: 'T/L'),
    'kepler_m': _mimic('kepler', lambda p, r: p.update(k=r.uniform(0.5, 2)),
                       lambda p, x: p['k'] / x['a'], lambda p: 'T*a'),
    'gas_m': _mimic('gas', lambda p, r: None,
                    lambda p, x: p['nR'] * 10000 * x['T'] / x['P'] ** 3, lambda p: 'P**3*V/T'),
    'lens_m': _mimic('lens', lambda p, r: p.update(K=p['f'] ** 2 * r.uniform(2, 4)),
                     lambda p, x: p['K'] / x['d1'], lambda p: 'd1*d2'),
    'spring_m': _mimic('spring', lambda p, r: None,
                       lambda p, x: p['w'] * x['x'], lambda p: 'v/x'),
    'energy_m': _mimic('energy', lambda p, r: p.update(c=r.uniform(5, 20)),
                       lambda p, x: p['c'] * p['H'] / x['h'], lambda p: 'v*h'),
    'coulomb_m': _mimic('coulomb', lambda p, r: None,
                        lambda p, x: 8.99e-3 / p['eps'] * x['q1'] * x['q2'] * x['r'] * 100, lambda p: 'F/(q1*q2*r)'),
    'ohm_m': _mimic('ohm', lambda p, r: p.update(R0=r.uniform(50, 200)),
                    lambda p, x: x['I'] * p['R0'] / x['R'], lambda p: 'U*R/I'),
    'kinetic_m': _mimic('kinetic', lambda p, r: p.update(c=r.uniform(1, 5)),
                        lambda p, x: p['c'] * x['m'] / x['v'], lambda p: 'E*v/m'),
}
MIMIC_ORDER = ['fall_m', 'pendulum_m', 'kepler_m', 'gas_m', 'lens_m', 'spring_m', 'energy_m', 'coulomb_m', 'ohm_m', 'kinetic_m']
W.LAWS.update(MIMIC)


def prior_in_names(inst, names):
    """Каноническое выражение знакомого закона X в именах ячейки (N — буквы)."""
    import re
    law = W.LAWS[inst['law']]
    e = law['prior'](inst['params'])
    if names == 'S':
        return e
    mp = inst['letters']
    return re.sub(r'\b[A-Za-z_][A-Za-z_0-9]*\b', lambda m: mp.get(m.group(0), m.group(0)), e)
