#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-04, шаг 3: производные числа записки POSTHOC-OCDIV-03.md из gha_out/ocdiv4_posthoc3/posthoc.json (для ledger.py audit).
  python3 posthoc_derived3.py    пишет posthoc_derived3.json рядом со скриптом"""
import json
import os

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
r = json.load(open(os.path.join(ROOT, 'gha_out/ocdiv4_posthoc3/posthoc.json'), encoding='utf-8'))
E = r['envs']
m100 = {n: E[n]['same_pairs_ood']['kinds'].get('−10^2', 0.0) for n in E}
pm10 = {n: E[n]['same_pairs_id']['kinds'].get('−10^1', 0.0) + E[n]['same_pairs_id']['kinds'].get('+10^1', 0.0) for n in E}
top = {}
for n in E:
    for h, v in E[n]['kinds_ood'].items():
        top.setdefault(h, {})[n] = v['kinds'].get('−10^2', 0.0)
der = dict(source='posthoc_derived3.py по gha_out/ocdiv4_posthoc3/posthoc.json',
           share_m100_same_ood=m100, share_m100_same_ood_min=min(m100.values()), share_m100_same_ood_max=max(m100.values()),
           share_pm10_same_id=pm10, share_pm10_same_id_min=min(pm10.values()), share_pm10_same_id_max=max(pm10.values()),
           share_m100_of_wrong_ood_by_head={h: dict(min=min(v.values()), max=max(v.values())) for h, v in top.items()},
           k_ood_minus_id_point=r['summary']['k_ood_minus_id']['delta'])
json.dump(der, open(os.path.join(X, 'posthoc_derived3.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps({k: der[k] for k in ('share_m100_same_ood_min', 'share_m100_same_ood_max', 'share_pm10_same_id_min', 'share_pm10_same_id_max')}))
print(json.dumps(der['share_m100_of_wrong_ood_by_head'], ensure_ascii=False))
