#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCINT-01: сверка ключевых чисел отчёта по ключам json. python3 check_report_ocint.py"""
import json
import os
import sys

import numpy as np

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
J = lambda p: json.load(open(os.path.join(ROOT, p), encoding='utf-8'))  # noqa: E731
rep = open(os.path.join(X, 'REPORT-OCINT-01.md'), encoding='utf-8').read()
w, r = J('gha_out/ocint_worlds/worlds.json'), J('gha_out/ocint_real/real.json')


def n(x, d=3, sign=False):
    s = f'{abs(x):.{d}f}'.replace('.', ',')
    if x < 0 and float(s.replace(',', '.')) != 0:
        return '−' + s
    return ('+' if sign and x > 0 else '') + s


ru, A_ = w['rules'], r['rule_A']
c = w['coverage']['0.9']
M, S = w['methods'], w['stats']
lim = [e['stats']['R2 wc CONF']['limit']['share_left'] for e in r['envs'].values()]
checks = [('вердикт А', f"А — «{A_['verdict']}»"), ('вердикт Б1', f"Б1 — «{ru['B1']['verdict']}»"), ('вердикт Б2', f"Б2 — «{ru['B2']['verdict']}»"),
          ('выбран', f"«{ru['choice']['chosen']}»"), ('медиана отношения А', n(A_['median_ratio'], 3)), ('знак А', f"{A_['same_sign']} средах из {A_['n_envs']}"),
          ('Б1 покрыто', f"{ru['B1']['covered']} опытах из {ru['B1']['n']}"), ('Б1 верхняя', n(ru['B1']['upper'], 3))]
for s_, v in ru['B2']['by_stat'].items():
    checks += [(f'Б2 {s_}', f"{v['covered']} из {v['n']} ({n(v['coverage'], 3)}; нижняя граница {n(v['lower'], 3)})")]
for m in M:
    for s_ in S:
        checks += [(f'покрытие {m.split()[0]} {s_.split()[0]}', f"{n(c['one_env'][m][s_]['coverage'], 3)} / {n(c['mean_of_worlds'][m][s_]['coverage'], 3)}")]
checks += [('предел мин', n(min(lim), 2)), ('предел макс', n(max(lim), 2)), ('предел медиана', n(float(np.median(lim)), 2)),
           ('разность ширины M4 − M6', n(ru['choice']['nearest']['diff'], 3, True)), ('время миров', n(w['seconds'], 0)), ('время сред', n(r['seconds'], 0))]
bad = [(k, v) for k, v in checks if v not in rep]
for k, v in checks:
    print(('✓ ' if v in rep else '✗ ') + f'{k}: {v}')
print(f'сверено {len(checks) - len(bad)} из {len(checks)}')
sys.exit(1 if bad else 0)
