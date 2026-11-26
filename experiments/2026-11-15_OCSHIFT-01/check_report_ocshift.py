#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCSHIFT-01: сверка ключевых чисел отчёта по ключам json (как в OCREP-01, совет 59). python3 check_report_ocshift.py
Для каждого числа: значение из json → то же форматирование, что в отчёте → строка должна быть в отчёте."""
import json
import os
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
J = lambda p: json.load(open(os.path.join(ROOT, p), encoding='utf-8'))  # noqa: E731
rep = open(os.path.join(X, 'REPORT-OCSHIFT-01.md'), encoding='utf-8').read()
r, fa, pw = J('gha_out/ocshift_test/analysis.json'), J('gha_out/ocshift_facts/facts_ocshift.json'), J('gha_out/ocshift_chain/power.json')


def n(x, d=3, sign=False):
    s = f'{abs(x):.{d}f}'.replace('.', ',')
    if x < 0 and float(s.replace(',', '.')) != 0:
        return '−' + s
    return ('+' if sign and x > 0 else '') + s


def ci(e, key='ci', d=4):
    return f"[{n(e[key][0], d, True)}; {n(e[key][1], d, True)}]"


D = lambda k: r[f'descr_{k}']  # noqa: E731
checks = [(f'вердикт {k}', f"«{r['verdicts'][k]}»") for k in ('R1', 'R2', 'R3', 'R4')]
checks += [(f'строгая ветвь {k}', f"«{r[k]['verdict_strict']}»") for k in ('R2', 'R3')]
for k in ('R1', 'R2', 'R3'):
    checks += [(f'{k}: Δ', n(r[k]['delta'], 4, True)), (f'{k}: BC', ci(r[k])), (f'{k}: процентильный', ci(r[k], 'ci_percentile')), (f'{k}: обратный', ci(r[k], 'ci_basic')),
               (f'{k}: z0', 'z₀ ' + n(r[k]['z0'], 3, True)), (f'{k}: сред того же знака', f"{r[k]['leave_one_range_out']['n_same_sign']} из {r[k]['leave_one_range_out']['n']}")]
checks += [('R2: нормальная граница', n(r['R2']['normal_bound']['upper'], 4, True)), ('R4: Q', n(r['R4']['Q'], 2)),
           ('D1: незнание', n(D('D1: разность незнания')['delta'], 4, True)), ('D1: самообман', n(D('D1: разность самообмана')['delta'], 4, True)),
           ('ИОИ ONE-BEST', n(fa['mean']['ONE-BEST']['ioi'])), ('ИОИ лучшего из восьми', n(fa['mean']['MIN8']['ioi'])), ('ИОИ CONF', n(fa['mean']['CONF']['ioi'])),
           ('ИОИ LR-AGREE', n(fa['mean']['LR-AGREE']['ioi'])), ('ONE-BEST − CONF', n(D('ONE-BEST − CONF')['delta'], 4, True)),
           ('FUSE-MIN − ONE-BEST', n(D('FUSE-MIN − ONE-BEST')['delta'], 4, True)), ('POST-IN CONF − CONF', n(D('POST-IN CONF − CONF')['delta'], 4, True)),
           ('LR-AGREE − AGREE', n(D('LR-AGREE − AGREE')['delta'], 4, True)), ('оракул', n(fa['mean_oracle'])),
           ('вес R2', n(pw['R2']['weight_bits'], 2, True)), ('вес R3, другая сторона', n(fa['other_side']['R3']['weight_bits'], 2, True)),
           ('вес R4', n(pw['R4']['weight_bits'], 2, True)), ('мощность R1', n(pw['R1']['reading_power'])), ('Брайер ожиданий', n(fa['brier_ocshift'], 3)),
           ('max-T: t', n(r['R1']['max_t']['t_max'], 2, True)), ('время анализа', n(r['seconds'], 1)), ('задач ID', str(fa['n_problems']['id'])), ('задач OOD', str(fa['n_problems']['ood']))]
bad = [(k, v) for k, v in checks if v not in rep]
for k, v in checks:
    print(('✓ ' if v in rep else '✗ ') + f'{k}: {v}')
print(f'сверено {len(checks) - len(bad)} из {len(checks)}')
sys.exit(1 if bad else 0)
