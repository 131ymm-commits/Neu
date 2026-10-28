#!/usr/bin/env python3
"""TRUST-03: числа отчёта из analysis_trust_03.json → facts_trust_03.json (вердиктов не меняет; записан после
регистрации 9137014, до просмотра результатов теста). Округление — 4 знака (u, w_G, лог-потеря), 5 знаков (части Прайса).
Запуск из папки опыта: python3 report_facts_trust03.py [папка с analysis, по умолчанию — опыт]"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, sys.argv[1]) if len(sys.argv) > 1 else HERE
a = json.load(open(os.path.join(DIR, 'analysis_trust_03.json')))
r4 = lambda x: round(float(x), 4)
r5 = lambda x: round(float(x), 5)
W_FAR, D = a['frozen']['W_FAR'], a['frozen']['D']
f = dict(verdicts={}, arms={}, price={}, summary=a['summary'], K1=a['construction_K1'], D2={})
for k, v in a['verdicts'].items():
    e = dict(outcome=v['outcome'], n=v['n'], k=v['k'])
    for key in ('value', 'diff', 'wG'):
        if key in v:
            e[key] = [r4(x) for x in v[key]]
    f['verdicts'][k] = e
for arm, m in a['arms'].items():
    f['arms'][arm] = dict(wG=[r4(x) for x in m['wG']], u=[r4((x - W_FAR) / D) for x in m['wG']],
                          logloss=[r4(x) for x in m['logloss']], b=[r4(x) for x in m['b']],
                          self_dec=[r4(x) for x in m['self_dec']], sd_groups=r4(m['wG_sd_groups'][0]))
for arm, m in a['descriptive_D1'].items():
    f['price'][arm] = dict(within=r5(m['within'][0]), between=r5(m['between'][0]), total=r5(m['total'][0]))
f['D2'] = dict(n_breakdown=a['descriptive_D2']['n_breakdown'], wG=[r4(x) for x in a['descriptive_D2']['wG']],
               u=[r4((x - W_FAR) / D) for x in a['descriptive_D2']['wG']])
f['per_seed_u'] = {arm: [r4((a['rows'][s][arm]['wG'] - W_FAR) / D) for s in sorted(a['rows'], key=int)]
                   for arm in ('MYOPIC', 'DEMES_NOSEL', 'DEMES', 'COUNCIL', 'DEMES_10x40', 'COUNCIL_10x40', 'DEMES_POOLED',
                               'DEMES_NOWITHIN', 'COUNCIL_IND', 'DEMES_IND')}
json.dump(f, open(os.path.join(DIR, 'facts_trust_03.json'), 'w'), ensure_ascii=False, indent=1)
for k, v in f['verdicts'].items():
    print(k, v)
print('сводные:', f['summary'])
print('Д2:', f['D2'])
