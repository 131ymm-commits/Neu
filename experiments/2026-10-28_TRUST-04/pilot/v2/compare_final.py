#!/usr/bin/env python3
"""TRUST-04: код регистрации против кода пилота v2 (третья проверка, находка 9): шесть ячеек пилота (зерно 1100) — нынешним
кодом, сверка итога и снимков с `pilot/v2/results_trust_04_*.json` бит в бит. Разница кодов — запись хешей, версий и docstring.
Запуск из папки опыта: OMP_NUM_THREADS=1 python3 pilot/v2/compare_final.py > pilot/v2/compare_final.log"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import exp_trust_04 as E  # noqa: E402

old = {}
for part in ('A', 'B'):
    for r in json.load(open(os.path.join(HERE, f'results_trust_04_{part}.json')))['runs']:
        old[(r['seed'], r['arm'])] = r
bad = 0; n = 0
for arm in ('DEMES_FREE', 'DEMES_NOWITHIN', 'DEMES_GPOOL', 'COUNCIL_SIGN', 'POOLED_MIG', 'DEMES_SIG5'):
    r = E.evolve4(1100, arm); o = old[(1100, arm)]
    for k, x in o['final'].items():
        n += 1; bad += r['final'][k] != x
    for t1, t2 in zip(o['traj'], r['traj']):
        for k, x in t1.items():
            n += 1; bad += t2[k] != x
    print(arm, 'итог w_G', r['final']['wG'], '— бит в бит' if r['final'] == o['final'] else '— РАСХОЖДЕНИЕ')
print(f'код {E.CODE_SHA256[:12]}…; сверено значений {n}, расхождений {bad}')
