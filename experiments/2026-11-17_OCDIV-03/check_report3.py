#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-03, совет 71 (Н9): сверка ключевых чисел отчёта по точному ключу json. Для каждого числа задан путь в analysis.json или в
notes_derived.json; число форматируется так же, как в report_ocdiv3.py, и ищется в REPORT-OCDIV-03.md. ledger.py audit ищет числа по
значению во всём файле и на плотном analysis.json даёт «неинформативно»; здесь проверяется, что в отчёте стоит именно значение поля.
  python3 check_report3.py            пишет check_report3.log рядом со скриптом; код выхода — число промахов"""
import json
import os
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
A = json.load(open(os.path.join(ROOT, 'gha_out/ocdiv3_sum_test/analysis.json'), encoding='utf-8'))
DER = json.load(open(os.path.join(X, 'notes_derived.json'), encoding='utf-8'))
REP = open(os.path.join(X, 'REPORT-OCDIV-03.md'), encoding='utf-8').read()


def f(x, d=4):                                  # то же, что report_ocdiv3.f
    return f'{x:+.{d}f}'.replace('-', '−').replace('.', ',')


def g(x, d=4):                                  # то же, что report_ocdiv3.g
    return f'{x:.{d}f}'.replace('.', ',')


def get(src, path):
    d = A if src == 'analysis' else DER
    for k in path:
        d = d[k]
    return d


CHECKS = []
for r in ('П1', 'П2', 'П3'):                                        # вердикты: точка и границы M4
    CHECKS += [(f'{r} Δ', 'analysis', (r, 'delta'), f),
               (f'{r} M4 нижняя', 'analysis', (r, 'ci', 0), f), (f'{r} M4 верхняя', 'analysis', (r, 'ci', 1), f)]
    CHECKS += [(f'{r} t по средам', 'derived', ('t_env', r), lambda x: g(x, 2))]
for n in ('T_X19_p3', 'T_X29_p3', 'T_X39_p3', 'T_X49_p3', 'T_X59_p3'):
    CHECKS += [(f'Т4 {n}', 'analysis', ('envs', n, 'T4', 'point'), f), (f'Т4ᵈ {n}', 'analysis', ('envs', n, 'T4d', 'point'), f),
               (f'Т4-ID {n}', 'analysis', ('envs', n, 'T4id', 'point'), f)]
CHECKS += [('интервал среды T_X49_p3 по П1, нижняя', 'derived', ('env_ci', 'П1', 'T_X49_p3', 0), f),
           ('интервал среды T_X49_p3 по П1, верхняя', 'derived', ('env_ci', 'П1', 'T_X49_p3', 1), f),
           ('та же нижняя граница в поле анализа env_lower', 'analysis', ('П1', 'env_lower', 'T_X49_p3'), f),
           ('порог t', 'derived', ('t_threshold',), lambda x: g(x, 3)),
           ('ложный уровень серии', 'derived', ('series_confirm',), g),
           ('F₀ вне диапазона, наименьшее', 'derived', ('F0_ood_min',), g), ('F₀ вне диапазона, наибольшее', 'derived', ('F0_ood_max',), g),
           ('F вне диапазона, наименьшее', 'derived', ('F_ood_min',), g), ('F вне диапазона, наибольшее', 'derived', ('F_ood_max',), g),
           ('F на ID, наибольшее', 'derived', ('F_id_max',), g),
           ('разложение: трудность по входу', 'analysis', ('descr_descr трудность по входу', 'delta'), f),
           ('разложение: совместность ошибок', 'analysis', ('descr_descr совместность ошибок', 'delta'), f),
           ('разложение: совпадение ответов', 'analysis', ('descr_descr совпадение ответов', 'delta'), f),
           ('совпадение ответов, нижняя', 'analysis', ('descr_descr совпадение ответов', 'ci', 0), f),
           ('совпадение ответов, верхняя', 'analysis', ('descr_descr совпадение ответов', 'ci', 1), f),
           ('Т4 − Т4-ID', 'analysis', ('descr_T4 − T4-ID', 'delta'), f),
           ('пары: p', 'analysis', ('pairs', 'p_exact'), g)]

miss, L = 0, []
for label, src, path, fmt in CHECKS:
    s = fmt(get(src, path))
    ok = s in REP
    miss += not ok
    L.append(f"{'✓' if ok else '✗'} {label}: {s} — {'analysis.json' if src == 'analysis' else 'notes_derived.json'} {'/'.join(map(str, path))}")
L.append(f'проверено: {len(CHECKS)}; промахов: {miss}')
open(os.path.join(X, 'check_report3.log'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\n'.join(L[-3:]))
sys.exit(miss)
