#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCREP-01 (совет 59): сверка ключевых чисел отчёта по ключам json — прямо из файлов анализа трёх опытов, мимо facts_ocrep.json.
Для каждого числа: значение из json → то же форматирование, что в отчёте → строка должна быть в REPORT-OCREP-01.md.
python3 check_report_ocrep.py"""
import json
import os
import sys

X = os.path.dirname(os.path.abspath(__file__))
J = lambda p: json.load(open(os.path.join(X, p), encoding='utf-8'))  # noqa: E731
rep = open(os.path.join(X, 'REPORT-OCREP-01.md'), encoding='utf-8').read()
r, oc, om = J('run/analysis.json'), J('../2026-11-14_OCCOR-01/run/analysis.json'), J('../2026-11-14_OCMIX-01/run/analysis.json')


def n(x, d=3, sign=False):
    s = f'{abs(x):.{d}f}'.replace('.', ',')
    if x < 0 and float(s.replace(',', '.')) != 0:
        return '−' + s
    return ('+' if sign and x > 0 else '') + s


def ci(e, key='ci', d=4):
    return f"[{n(e[key][0], d, True)}; {n(e[key][1], d, True)}]"


checks = [
    ('R1: Δ', n(r['R1']['delta'], 4, True)), ('R1: ДИ BC', ci(r['R1'])), ('R1: ДИ процентильный', ci(r['R1'], 'ci_percentile')),
    ('R2: Δ', n(r['R2']['delta'], 4, True)), ('R2: ДИ BC', ci(r['R2'])), ('R2: ДИ процентильный', ci(r['R2'], 'ci_percentile')),
    ('CONF − LR-AGREE: Δ', n(r['descr_CONF−LR']['delta'], 4)), ('CONF − LR-AGREE: ДИ BC', ci(r['descr_CONF−LR'])),
    ('CONF − LR-AGREE: ДИ процентильный', ci(r['descr_CONF−LR'], 'ci_percentile')),
    ('ΔC R1: Δ', n(r['descr_R1_dC']['delta'], 4, True)), ('ΔC R1: ДИ BC', ci(r['descr_R1_dC'])),
]
for name, a in (('OCCOR-01', oc), ('OCMIX-01', om), ('OCREP-01', r)):
    for e in ('AGREE', 'LR-AGREE'):
        checks.append((f'ИОИ {e}, {name}', n(a['evaluators'][e]['ioi'])))
checks += [('C-086 OCCOR-01: Δ', n(oc['R1']['delta'], 4)), ('C-086 OCMIX-01: Δ', n(om['R3']['delta'], 4))]
bad = [(name, s) for name, s in checks if s not in rep]
for name, s in checks:
    print(('✓ ' if (name, s) not in bad else '✗ ') + f'{name}: {s}')
print('сверено:', len(checks), '| не найдено в отчёте:', len(bad))
sys.exit(1 if bad else 0)
