#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-04: сверка ключевых чисел отчёта по точному ключу — каждое число вердиктов, ветви, сред и описательного печатается тем же
форматом, что в report_ocdiv4.py, из analysis.json и ищется в тексте REPORT-OCDIV-04.md. Пишет check_report4.log; выход 1 при пропуске.
  python3 check_report4.py"""
import json
import os
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
sys.path.insert(0, X)
import report_ocdiv4 as RP  # noqa: E402

A = json.load(open(os.path.join(ROOT, 'gha_out/ocdiv4_sum_test/analysis.json'), encoding='utf-8'))
EX = json.load(open(os.path.join(X, 'expect_ocdiv4.json'), encoding='utf-8'))
md = open(os.path.join(X, 'REPORT-OCDIV-04.md'), encoding='utf-8').read()
checks = []


def need(name, s):
    checks.append((name, s, s in md))


for src, rules in (('rules', A['rules']), ('rules_alt', A['rules_alt'])):
    for r, e in rules.items():
        need(f'{src}.{r}.delta', RP.f(e['delta']))
        need(f'{src}.{r}.ci', f"[{RP.f(e['ci'][0])}; {RP.f(e['ci'][1])}]")
        need(f'{src}.{r}.t', RP.g(e['t_envs']['t'], 2))
        need(f'{src}.{r}.crit', RP.g(e['t_envs']['crit'], 3))
        need(f'{src}.{r}.verdict', e['verdict_rule'])
for fam, F in A['families'].items():
    for n, e in F['envs'].items():
        for key in ('d3c_ood', 'n0c_ood', 'd3c_id', 'k_ood', 'k_id', 't4_ood'):
            need(f'{fam}.{n}.{key}', f"{RP.f(e[key]['point'])} ({RP.g(e[key]['sd'])})")
for k in ('thousands d3u_ood', 'length d3u_ood', 'thousands k_ood', 'thousands k_id', 'length k_ood', 'length k_id', 'thousands d3c_id', 'length d3c_id'):
    need(f'descr.{k}', RP.f(A['descr'][k]['delta']))
for e in EX['expectations']:
    got = RP.outcome(A, e['key'])
    need(f"expect.{e['id']}", f"| {e['id']} | {e['text']} | {RP.g(e['p'], 4 if e['p'] < 0.01 else 3)} | {'да' if got else 'нет'} |")
bad = [c for c in checks if not c[2]]
log = [f"{'✓' if ok else '✗'} {name}: {s}" for name, s, ok in checks] + [f'проверок: {len(checks)}; пропусков: {len(bad)}']
open(os.path.join(X, 'check_report4.log'), 'w', encoding='utf-8').write('\n'.join(log) + '\n')
print(log[-1])
sys.exit(1 if bad else 0)
