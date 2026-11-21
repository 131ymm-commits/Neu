#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCREP-01: производные числа для отчёта → <папка анализа>/facts_ocrep.json (чтобы ledger.py audit находил каждое число
отчёта в данных). python3 facts_ocrep.py [ANALYSIS.json]  (по умолчанию run/analysis.json)
Источники — анализ теста, analysis_pilot.json, power.json, expectations.json, OCCOR-01 и OCMIX-01 run/analysis.json и power.json.
Код написан до данных теста и проверен на прогоне правил по ответам пилота (pilot/analysis_test_rules_on_pilot.json)."""
import json
import os
import sys
from math import erf, sqrt

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
J = lambda p: json.load(open(p if os.path.isabs(p) else os.path.join(HERE, p), encoding='utf-8'))  # noqa: E731
Phi = lambda z: 0.5 * (1 + erf(z / sqrt(2)))          # noqa: E731


def main(src='run/analysis.json'):
    r, p, pw = J(src), J('analysis_pilot.json'), J('power.json')
    oc, om = J('../2026-11-14_OCCOR-01/run/analysis.json'), J('../2026-11-14_OCMIX-01/run/analysis.json')
    ocpw, ompw = J('../2026-11-14_OCCOR-01/power.json'), J('../2026-11-14_OCMIX-01/power.json')
    E = r['evaluators']
    out = dict(source=src)
    out['n_test'] = r['n_id'] + r['n_ood']
    out['rule_ci_coverage'] = 1 - 2 * r['level']
    top = {e: v['top10_sel']['deception'] for e, v in E.items()}
    out['top10_sel_deception'] = top
    out['top10_sel_range'] = dict(min=min(top.values()), max=max(top.values()))
    out['top10_sel_n'] = E['AGREE']['top10_sel']['n']
    out['top10_boundary_block_AGREE'] = E['AGREE']['top10_sel']['boundary_block']
    out['c088_transfer_AGREE_top'] = dict(occor=oc['evaluators']['AGREE']['top10_sel']['deception'],
                                          ocmix=om['evaluators']['AGREE']['top10_sel']['deception'], ocrep=top['AGREE'])
    out['ioi'] = {e: v['ioi'] for e, v in E.items()}
    out['ioi_rank'] = sorted(E, key=lambda e: E[e]['ioi'])
    out['auroc_mean'] = {e: float(np.mean(v['auroc_ood'])) for e, v in E.items()}
    out['pilot_vs_test_rules'] = {k: dict(pilot=p['deltas'][k]['point'], test=r[k]['delta']) for k in ('R1', 'R2')}
    out['pilot_vs_test_rules']['R3'] = dict(pilot=p['deltas']['R3']['point'], test=r['descr_R3_descr']['delta'])
    out['pilot_vs_test_ioi'] = {e: dict(pilot=p['full'][e]['ioi'], test=E[e]['ioi']) for e in E}
    # C-086 по трём сдвигам: Δ ИОИ LR-AGREE − AGREE и ДИ (у каждого — свой уровень правил)
    out['c086_three_shifts'] = dict(occor=dict(delta=oc['R1']['delta'], ci=oc['R1']['ci'], ci_percentile=oc['R1']['ci_percentile']),
                                    ocmix=dict(delta=om['R3']['delta'], ci=om['R3']['ci'], ci_percentile=om['R3']['ci_percentile']),
                                    ocrep=dict(delta=r['R1']['delta'], ci=r['R1']['ci'], ci_percentile=r['R1']['ci_percentile']))
    out['c087_two_shifts'] = dict(occor=dict(delta=oc['R3']['delta'], ci=oc['R3']['ci']), ocrep=dict(delta=r['R2']['delta'], ci=r['R2']['ci']))
    # квантили BC правил на этих данных: Φ(2·z0 ± z), z — уровня правил
    zr = pw['z']
    out['bc_quantiles'] = {k: [Phi(2 * r[k]['z0'] - zr), Phi(2 * r[k]['z0'] + zr)] for k in r['rules']}
    sup_any, sup_other = E['VETO']['selected_supported'], r['support_other_lineage_descr']['VETO']
    out['veto_support_split'] = dict(any=sup_any, other_lineage=sup_other, only_relatives=sup_any - sup_other, none=1 - sup_any)
    out['unsupported_id_total'] = int(sum(v['unsupported_id'] for v in r['head_counts'].values()))
    out['min_count'] = int(min(min(v['id_correct'], v['id_wrong'], v['ood_correct'], v['ood_wrong']) for v in r['method']['counts'].values()))
    out['tie_frac_range'] = dict(min=min(v['tie_frac'] for v in E.values()), max=max(v['tie_frac'] for v in E.values()))
    base = float(np.log2(0.54 / 0.46))                    # база класса «гипотеза_neu» (tools/support_bits.py)
    out['support_bits'] = dict(base_hypothesis_neu=base, occor_R1=ocpw['R1']['weight_bits'], ocmix_R3=ompw['R3']['weight_bits'],
                               ocrep_R1=pw['R1']['weight_bits'], ocrep_R2=pw['R2']['weight_bits'],
                               c086_before=base + ocpw['R1']['weight_bits'] + ompw['R3']['weight_bits'])
    out['power_reading'] = {k: pw[k]['reading_power'] for k in ('R1', 'R2')}
    out['mde_conj'] = {k: dict(confirm=pw[k]['conj']['mde_confirm_power08'], refute=pw[k]['conj']['mde_refute_power08']) for k in ('R1', 'R2')}
    # Пост-хок (дописано после данных теста; вердикт не меняет; DEVIATIONS.md): ИОИ, самообман и точность выбора оценщиков
    # по трём сдвигам — какой оценщик лучший и скромнее ли LR-AGREE, как в OCCOR-01 и OCMIX-01.
    ev = ('AGREE', 'LR-AGREE', 'NB-IND', 'CONF', 'VETO', 'MIX-LR')
    out['cross_shift_posthoc'] = {name: {e: dict(ioi=a_['evaluators'][e]['ioi'], deception=a_['evaluators'][e]['deception'], T=a_['evaluators'][e]['T'])
                                         for e in ev if e in a_['evaluators']} for name, a_ in (('OCCOR-01', oc), ('OCMIX-01', om), ('OCREP-01', r))}
    out['best_ioi_posthoc'] = {name: min(v, key=lambda e: v[e]['ioi']) for name, v in out['cross_shift_posthoc'].items()}
    ans = os.path.join(os.path.dirname(src if os.path.isabs(src) else os.path.join(HERE, src)), 'out', 'answers.json')
    if os.path.isfile(ans):
        out['task'] = json.load(open(ans, encoding='utf-8'))['task']      # границы задачи и зёрна — из вывода извлечения
    import re
    lg = os.path.join(os.path.dirname(src if os.path.isabs(src) else os.path.join(HERE, src)), 'analysis.log')
    if os.path.isfile(lg):
        m = re.search(r'real\s+(\d+)m([\d.]+)s', open(lg, encoding='utf-8').read())
        if m:
            out['analysis_seconds'] = int(m.group(1)) * 60 + float(m.group(2))
    out['lower_dist_posthoc'] = {k: dict(test=r[k]['delta'] - r[k]['ci'][0], predicted=pw[k]['conj']['lower'], z0_test=r[k]['z0'],
                                         z0_pilot_chain=pw[k]['conj']['z0_pilot_chain'], bc_lower_quantile_pilot=pw[k]['conj']['bc_quantiles'][0])
                                 for k in ('R1', 'R2')}
    # Совет 59 (пост-хок к отчёту, вердикт не меняет): время извлечения из журнала Kaggle; число описательных сравнений и
    # общий ложный уровень их серии (Бонферрони, оценка сверху); мощность C-087 в OCCOR-01 (возможное завышение прежних эффектов).
    kl = os.path.join(os.path.dirname(src if os.path.isabs(src) else os.path.join(HERE, src)), 'out', 'kaggle_log.json')
    if os.path.isfile(kl):
        m = [re.search(r'\[\s*([\d.]+)\s*с\]\s*готово', e['data']) for e in json.load(open(kl, encoding='utf-8')) if e['stream_name'] == 'stdout']
        m = [x for x in m if x]
        if m:
            out['extraction_seconds'] = float(m[-1].group(1))
    nd = [k for k, v in r.items() if k.startswith('descr_') and isinstance(v, dict) and 'ci' in v]
    out['descr_count'] = len(nd)
    out['descr_family_level_bonferroni'] = len(nd) * 2 * r['descr_level']
    out['occor_c087_power_half'] = ocpw['R3']['power']['ужатый вдвое']
    out['expectations_prereg'] = dict(source='PREREG-OCREP-01 §7 (копия таблицы)', E1=0.04, E2=0.04, E3=0.02, E4=0.06, E5=0.97, E6=0.93, E7=0.45,
                                      E8=0.90, E9=0.85, E10=0.04)
    oc_ = dict(E1=int(r['R1']['verdict'] == 'подтверждено'), E2=int(r['R1']['verdict'] == 'опровергнуто'), E3=int(r['R2']['verdict'] == 'подтверждено'),
               E4=int(r['R2']['verdict'] == 'опровергнуто'), E5=int(r['method']['ok']),
               E6=int(r['prior_effect_descr']['R1']['OCMIX-01 R3']['status'] == 'исключён'),
               E7=int(r['prior_effect_descr']['R1']['половина наименьшего']['status'] == 'исключён'),
               E8=int(top['AGREE'] < 0.10), E9=int(E['VETO']['selected_supported'] >= 0.95), E10=int(r['R1']['verdict'] == 'не решено (только BC)'))
    out['expectations_outcome'] = oc_
    ex = out['expectations_prereg']
    out['brier_ocrep'] = float(np.mean([(ex[k] - oc_[k]) ** 2 for k in oc_]))
    dst = os.path.join(os.path.dirname(src if os.path.isabs(src) else os.path.join(HERE, src)), 'facts_ocrep.json')
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'run/analysis.json')
