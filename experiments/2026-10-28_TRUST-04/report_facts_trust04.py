#!/usr/bin/env python3
"""TRUST-04: числа отчёта из analysis_trust_04.json → facts_trust_04.json (вердиктов не меняет; записан до регистрации и
до теста). Округление — 4 знака (u, w_G, лог-потеря, R, SD), 5 знаков (части Прайса).
Запуск из папки опыта: python3 report_facts_trust04.py [папка с analysis, по умолчанию — опыт]"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, sys.argv[1]) if len(sys.argv) > 1 else HERE
a = json.load(open(os.path.join(DIR, 'analysis_trust_04.json')))
r4 = lambda x: None if x is None else round(float(x), 4)
r5 = lambda x: round(float(x), 5)
L4 = lambda xs: [r4(x) for x in xs]


def verdict(v):
    e = dict(outcome=v['outcome'], kind=v['kind'])
    for key in ('k', 'n', 'N', 'n_min', 'breakdowns'):
        if key in v:
            e[key] = v[key]
    for key in ('value', 'diff', 'diff_ci', 'value_no_breakdown', 'u_indep', 'u_main'):
        if v.get(key) is not None:
            e[key] = L4(v[key])
    for key in ('sd_IND', 'sd_base', 'p_one_sided', 'spearman', 'spearman_p_two_sided'):
        if key in v:
            e[key] = r4(v[key])
    for key in ('u', 'one_minus_R', 'abs_gap'):
        if key in v and isinstance(v[key], list):
            e[key] = L4(v[key])
    if 'n_within_01' in v:
        e['n_within_01'] = v['n_within_01']
    return e


f = dict(verdicts={k: verdict(v) for k, v in a['verdicts'].items()}, explore={k: verdict(v) for k, v in a['explore'].items()},
         summary=a['summary'], n_seeds=a['n_seeds'], seeds=[a['seeds'][0], a['seeds'][-1]], code_sha256=a.get('code_sha256'),
         arms={}, step_sd={k: r4(v[0]) for k, v in a['step_sd'].items()},
         breakdowns={k: dict(n=v['n_break'], seeds=v['seeds_break'], V_within=L4(v['V_within_break']), u=L4(v['u_break']),
                             V_within_ok=r4(v['V_within_ok'][0])) for k, v in a['breakdowns'].items()},
         construction={k: dict(logloss_gap=L4(v['logloss_gap']), n_gap_ge_002=v['n_gap_ge_002'], wG=L4(v['wG']),
                               sd_groups=L4(v['sd_groups'])) for k, v in a['construction'].items()},
         price={k: dict(within=r5(v['within'][0]), between=r5(v['between'][0])) for k, v in a['descriptive_price'].items()},
         indep=None if a['indep'] is None else dict(seeds=[a['indep']['seeds'][0], a['indep']['seeds'][-1]], n=a['indep']['n']))
for arm, m in a['arms'].items():
    f['arms'][arm] = {k: L4(m[k]) for k in ('u', 'wG', 'logloss', 'acc', 'self_dec', 'b', 'wG_sd_groups', 'R', 'step_sd', 'V_between', 'V_within')}
json.dump(f, open(os.path.join(DIR, 'facts_trust_04.json'), 'w'), ensure_ascii=False, indent=1)
for k, v in list(f['verdicts'].items()) + list(f['explore'].items()):
    print(k, v['outcome'], {kk: vv for kk, vv in v.items() if kk not in ('outcome', 'kind')})
print('сводные:', f['summary'])
print('срывы:', {k: (v['n'], v['seeds']) for k, v in f['breakdowns'].items() if v['n']})
