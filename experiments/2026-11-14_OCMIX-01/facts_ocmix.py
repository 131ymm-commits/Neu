#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCMIX-01: производные числа для отчёта → run/facts_ocmix.json (чтобы ledger.py audit находил каждое число отчёта в данных).
Источники — run/analysis.json (тест), analysis_pilot.json (пилот), power.json, OCCOR-01 run/analysis.json (для C-088).
Пост-хок (записан после данных теста, вердикт не меняет): сравнение верхушки с OCCOR-01; пилот против теста; итог веса опоры."""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
J = lambda p: json.load(open(os.path.join(HERE, p), encoding='utf-8'))  # noqa: E731
r, p, pw = J('run/analysis.json'), J('analysis_pilot.json'), J('power.json')
oc = J('../2026-11-14_OCCOR-01/run/analysis.json')
ocpw = J('../2026-11-14_OCCOR-01/power.json')
E = r['evaluators']
out = {}
top = {e: v['top10_sel']['deception'] for e, v in E.items()}
out['top10_sel_deception'] = top
out['top10_sel_range'] = dict(min=min(top.values()), max=max(top.values()))
out['top10_sel_n'] = E['AGREE']['top10_sel']['n']
ocs = {e: oc['evaluators'][e]['top10_sel']['deception'] for e in ('AGREE', 'LR-AGREE', 'CONF')}
out['occor_top10_sel_deception'] = ocs
out['occor_vs_ocmix_top_AGREE'] = dict(occor=ocs['AGREE'], ocmix=top['AGREE'], diff=top['AGREE'] - ocs['AGREE'])
out['pilot_vs_test_rules'] = {k: dict(pilot=p['deltas'][h]['point'], test=r[k]['delta']) for k, h in (('R1', 'H1'), ('R2', 'H2'), ('R3', 'H3'))}
out['pilot_vs_test_ioi'] = {e: dict(pilot=p['full'][e]['ioi'], test=E[e]['ioi']) for e in E}
base = float(np.log2(0.54 / 0.46))                    # база класса «гипотеза_neu» (tools/support_bits.py)
out['support_bits'] = dict(base_hypothesis_neu=base, R3_weight=pw['R3']['weight_bits'],
                           occor_R1_weight=ocpw['R1']['weight_bits'], C086_total_two_groups=base + ocpw['R1']['weight_bits'] + pw['R3']['weight_bits'])
out['auroc_mean'] = {e: float(np.mean(v['auroc_ood'])) for e, v in E.items()}
out['unsupported_id_total'] = int(sum(v['unsupported_id'] for v in r['head_counts'].values()))
out['expectations_prereg'] = dict(source='PREREG-OCMIX-01 §7 (копия таблицы)', E1=0.01, E2=0.002, E3=0.35, E4=0.95, E5=0.85, E6=0.90, E7=0.90)
sup_any, sup_other = E['VETO']['selected_supported'], r['support_other_lineage_descr']['VETO']
out['veto_support_split'] = dict(any=sup_any, other_lineage=sup_other, only_relatives=sup_any - sup_other, none=1 - sup_any,
                                 note='совет 57: only_relatives — поддержка была, но только от родственных голов (свои чекпойнты или своя пара с deduped); none — поддержки не было')
ex = out['expectations_prereg']
oc_ = dict(E1=0, E2=0, E3=1, E4=1, E5=1, E6=1, E7=1)                  # исходы по REPORT-OCMIX-01 §3
br = lambda ks: float(np.mean([(ex[k] - oc_[k]) ** 2 for k in ks]))  # noqa: E731
out['brier_ocmix'] = dict(all_7=br(['E1', 'E2', 'E3', 'E4', 'E5', 'E6', 'E7']), without_post_pilot=br(['E1', 'E2', 'E3', 'E4', 'E6']),
                          note='совет 57: без помеченных «после пилота» E5 и E7')
out['n_test'] = r['n_id'] + r['n_ood']
out['rule_ci_coverage'] = 1 - 2 * r['level']
out['mde_power08'] = {k: pw[k]['mde_power08'] for k in ('R1', 'R2', 'R3')}
json.dump(out, open(os.path.join(HERE, 'run', 'facts_ocmix.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
