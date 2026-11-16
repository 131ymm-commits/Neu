#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCPOST-01: сверка ключевых чисел отчёта по ключам json (как в OCSHIFT-01 и OCINT-01). Для каждого числа: значение из json →
то же форматирование, что в отчёте → строка должна быть в отчёте. Числа свободного текста дополнительно сверяет ledger.py audit.
  python3 check_report_ocpost.py [ANALYSIS.json TAIL.json FACTS.json REPORT.md]
По умолчанию: gha_out/ocpost_test/analysis.json, gha_out/ocpost_tail_sum/tail.json, gha_out/ocpost_facts/facts_ocpost.json,
REPORT-OCPOST-01.md рядом со скриптом."""
import json
import os
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
a = sys.argv[1:]
P = lambda p: p if os.path.isabs(p) else os.path.join(ROOT, p)  # noqa: E731
J = lambda p: json.load(open(P(p), encoding='utf-8'))  # noqa: E731
an = J(a[0] if a else 'gha_out/ocpost_test/analysis.json')
tl = J(a[1] if len(a) > 1 else 'gha_out/ocpost_tail_sum/tail.json')
fc = J(a[2] if len(a) > 2 else 'gha_out/ocpost_facts/facts_ocpost.json')
rep = open(a[3] if len(a) > 3 else os.path.join(X, 'REPORT-OCPOST-01.md'), encoding='utf-8').read()
RULE_TEXT = {'P0': 'wc CONF (повтор C-090)', 'P1': 'ИОИ POST-CV − ИОИ CONF', 'P2': 'ИОИ POST-CV − ИОИ ONE-BEST',
             'P3': 'wc POST (полоса ±0,02)', 'N': 'wc FIXED (полоса ±0,02)'}


def n(x, d=4, sign=True):                     # то же, что report_ocpost.n
    if x is None:
        return '—'
    s = f'{abs(x):.{d}f}'.replace('.', ',')
    if x < 0 and float(s.replace(',', '.')) != 0:
        return '−' + s
    return ('+' if sign and x > 0 and float(s.replace(',', '.')) != 0 else '') + s


def iv(ci, d=4):
    return f'[{n(ci[0], d)}; {n(ci[1], d)}]'


checks = []
for k in ('P0', 'P1', 'P2', 'P3', 'N'):
    e = an[k]
    checks += [(f'{k}: строка итога', f"| {k} | {RULE_TEXT[k]} | {n(e['delta'])} | {iv(e['ci'])} | {e['verdict']} |"),
               (f'{k}: вес', f"{n(fc['weights'][k]['bits'], 2, False)} бит")]
checks += [('Т: вердикт', f"| {tl['verdict']} | 0 бит (проверка метода) |"), ('Т: миров', f"({tl['n_worlds']} миров)")]
for s_, e in tl['stats'].items():
    checks += [(f'Т {s_}: промахи и границы', f"| {s_} | {e['n']} | {e['n_nan']} | {e['miss_low']} | {n(e['upper_low'], 4, False)} | "
                                              f"{e['miss_high']} | {n(e['upper_high'], 4, False)} |")]
ch = an.get('check') or {}
checks += [('сверка цепочки', f"наибольшее расхождение logp {n(ch.get('max_abs_dlogp', 0), 6, False)}"),
           ('годных сред', f"Годных сред {an['method']['n_valid']} из {an['method']['n_envs']}"), ('повторов', f"B = {an['B']} повторов"),
           ('время анализа', f"{n(an['seconds'], 0, False)} с")]
for k in ('P0', 'P1', 'P2'):
    g = an[k].get('leave_one_range_out')
    if g:
        checks += [(f'{k}: без одного диапазона', f"сред того же знака {g['n_same_sign']} из {g['n']}")]
for k, key in (('P1', 'brier_reading'), ('P2', 'brier_reading'), ('P2', 'ood_deception_reading')):
    r = an[k].get(key)
    if r:
        checks += [(f'{k}: {key}', iv(r['ci']))]
for e_ in ('CONF', 'POST-CV', 'ONE-BEST', 'FIXED', 'SHIFT'):
    p_ = fc['parts_mean'][e_]
    checks += [(f'части {e_}', f"| {e_} | {n(p_['T'], 4, False)} | {n(p_['C'], 4, False)} | {n(p_['ign'], 4, False)} | {n(p_['dec'], 4, False)} | "
                                f"{n(p_['ioi'], 4, False)} | {n(p_['brier'], 4, False)} |")]
for nm in an['method']['valid']:
    re_ = an['envs'][nm]['rules_env']
    checks += [(f'среда {nm}', f"| {nm} | " + ' | '.join(f"{n(re_[k]['point'])} ({n(re_[k]['sd'], 4, False)})" for k in ('P0', 'P1', 'P2', 'P3', 'N')))]
for k, e in an.items():
    if k.startswith('descr_'):
        checks += [(f'описательно {k[6:]}', f"| {k[6:]} | {n(e['delta'])} | {iv(e['ci'])} |")]
for k in ('P0', 'P1', 'P2', 'P3'):
    w, fl = fc['weights'][k], fc['false_level'][k]
    checks += [(f'{k}: ложный уровень', f"ложный уровень {n(fl['value'], 4, False)} ({fl['side']})")]
bad = [(k, v) for k, v in checks if v not in rep]
for k, v in checks:
    print(('✓ ' if v in rep else '✗ ') + f'{k}: {v}')
print(f'сверено {len(checks) - len(bad)} из {len(checks)}')
sys.exit(1 if bad else 0)
