#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCCOR-01: производные числа для отчёта → facts_occor.json (чтобы ledger.py audit находил каждое число отчёта в данных).
Источники — run/analysis.json (тест), analysis_pilot.json (пилот), power.json.
Пост-хок (записан после данных теста, вердикт не меняет; в PREREG этих величин нет):
  - разложение R3 на ΔT и ΔC и доля C (как разложение R1 в PREREG §5);
  - средний AUROC по головам и число голов, где AUROC LR-AGREE выше, чем у AGREE и у CONF;
  - пилот против теста по ИОИ оценщиков и по разностям правил."""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
r = json.load(open(os.path.join(HERE, 'run', 'analysis.json'), encoding='utf-8'))
p = json.load(open(os.path.join(HERE, 'analysis_pilot.json'), encoding='utf-8'))
pw = json.load(open(os.path.join(HERE, 'power.json'), encoding='utf-8'))
E = r['evaluators']
out = {}
dT3, dC3 = E['LR-AGREE']['T'] - E['NB-IND']['T'], E['LR-AGREE']['C'] - E['NB-IND']['C']
dI3 = E['LR-AGREE']['ioi'] - E['NB-IND']['ioi']
out['posthoc_R3_decomposition'] = dict(dT=dT3, dC=dC3, dIOI=dI3, share_C=dC3 / dI3,
                                       note='пост-хок: при самообмане > 0 у обоих ΔИОИ = −2ΔT + ΔC; вердикт не меняет')
out['auroc_mean'] = {e: float(np.mean(v['auroc_ood'])) for e, v in E.items()}
la, aa, ca = E['LR-AGREE']['auroc_ood'], E['AGREE']['auroc_ood'], E['CONF']['auroc_ood']
out['auroc_heads'] = dict(n=len(la), LR_gt_AGREE=int(sum(x > y for x, y in zip(la, aa))), LR_gt_CONF=int(sum(x > y for x, y in zip(la, ca))),
                          CONF_gt_LR=[r['heads'][k] for k in range(len(la)) if ca[k] > la[k]])
out['pilot_vs_test_ioi'] = {e: dict(pilot=p['full'][e]['ioi'], test=E[e]['ioi'], diff=E[e]['ioi'] - p['full'][e]['ioi']) for e in E}
src = {'R1': 'LR-AGREE−AGREE', 'R2': 'NB-AGREE−AGREE', 'R3': 'LR-AGREE−NB-IND'}
out['pilot_vs_test_rules'] = {k: dict(pilot=p['full_delta'][v]['point'], test=r[k]['delta']) for k, v in src.items()}
out['pilot_vs_test_rules']['R4'] = dict(pilot_all_crowds=p['dose_contrast']['LR-AGREE']['point'], test_fixed_crowds=r['R4']['delta'])
out['weights_bits'] = {k: pw[k]['weight_bits'] for k in ('R1', 'R2', 'R3', 'R4')}
out['top10_sel_deception'] = {e: v['top10_sel']['deception'] for e, v in E.items()}
out['top10_sel_n'] = E['AGREE']['top10_sel']['n']
base = float(np.log2(0.54 / 0.46))                    # база класса «гипотеза_neu» (tools/support_bits.py)
out['support_bits'] = dict(base_hypothesis_neu=base, R1_total=base + pw['R1']['weight_bits'], R3_total=base + pw['R3']['weight_bits'])
out['n_test'] = r['n_id'] + r['n_ood']
out['rule_ci_coverage'] = 1 - 2 * r['level']          # двусторонний ДИ правил при уровне 0,0025 на сторону
json.dump(out, open(os.path.join(HERE, 'run', 'facts_occor.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
