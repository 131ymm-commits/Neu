#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCGEO-01: числа отчёта из run/analysis.json, run/out/answers.json и power.json → facts_ocgeo.json. Ожидания §7 ставит код."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
a = json.load(open(os.path.join(HERE, 'run', 'analysis.json'), encoding='utf-8'))
pw = json.load(open(os.path.join(HERE, 'power.json'), encoding='utf-8'))
ans = json.load(open(os.path.join(HERE, 'run', 'out', 'answers.json'), encoding='utf-8'))
pil = json.load(open(os.path.join(HERE, 'pilot1', 'analysis_test_rules_on_pilot.json'), encoding='utf-8'))
r3 = lambda x: None if x is None else round(float(x), 3)          # noqa: E731
r4 = lambda x: None if x is None else round(float(x), 4)          # noqa: E731
ev = a['evaluators']
top = a['top10_pairs_descr']
nt = a['no_twins_descr']['evaluators']
exp = {'E1': int(a['P1']['verdict'] == 'опровергнуто'), 'E2': int(a['P2_descr']['delta'] < 0),
       'E3': int(a['P3']['verdict'] == 'подтверждено'), 'E4': int(a['method']['ok']),
       'E5': int(ev['GEO']['deception'] > ev['AGREE']['deception']), 'E6': int(ev['INPUT']['ioi'] < ev['GEO']['ioi']),
       'E7': int(top['GEO']['deception'] - top['AGREE']['deception'] >= 0.05),
       'E8': int(min(nt, key=lambda e: nt[e]['ioi']) != 'AGREE')}
P = {'E1': 0.9, 'E2': 0.6, 'E3': 0.9, 'E4': 0.95, 'E5': 0.85, 'E6': 0.8, 'E7': 0.85, 'E8': 0.7}
brier = sum((P[k] - v) ** 2 for k, v in exp.items()) / len(exp)
w = {'P1': pw['P1']['weight_bits'] if a['P1']['verdict'] == 'опровергнуто' else 0.0,
     'P3': pw['P3']['weight_bits'] if a['P3']['verdict'] == 'подтверждено' else 0.0}
out = dict(
    verdict=a['verdict'], verdicts=a['verdicts'], method_ok=a['method']['ok'], n_id=a['n_id'], n_ood=a['n_ood'],
    run_seconds=round(ans['seconds']), info=ans['info'],
    accuracy={h: {k: r3(v) for k, v in x.items()} for h, x in a['accuracy'].items()},
    evaluators={e: {k: r3(v) for k, v in x.items()} for e, x in ev.items()},
    P1=dict(delta=r3(a['P1']['delta']), ci99=[r3(x) for x in a['P1']['ci99']]),
    P3=dict(delta=r3(a['P3']['delta']), ci99=[r4(x) for x in a['P3']['ci99']], per_head=[r3(x) for x in a['P3']['per_head']]),
    P2_descr=dict(delta=r3(a['P2_descr']['delta']), ci99=[r3(x) for x in a['P2_descr']['ci99']]),
    geo_minus_input=dict(delta=r3(a['geo_minus_input_descr']['delta']), ci99=[r3(x) for x in a['geo_minus_input_descr']['ci99']]),
    auroc_ood={e: [r3(x) for x in v] for e, v in a['auroc_ood'].items()},
    auroc_ood_range={e: [r3(min(v)), r3(max(v))] for e, v in a['auroc_ood'].items()},
    top10={e: {k: (r3(v) if isinstance(v, float) else v) for k, v in x.items()} for e, x in top.items()},
    no_twins={e: r3(x['ioi']) for e, x in nt.items()},
    subset_curve={r: {e: r3(v['ioi']) for e, v in x.items()} for r, x in a['subset_curve_descr'].items()},
    grid_vs_baseline=dict(baseline=round(a['best_head_no_evaluator']['ioi'], 5),
                          best=min(((round(v['geo_ioi'], 5), k) for k, v in a['grid_descr'].items())),
                          worse_than_baseline=sum(v['geo_ioi'] > a['best_head_no_evaluator']['ioi'] for v in a['grid_descr'].values()),
                          chosen_rank=sorted(v['geo_ioi'] for v in a['grid_descr'].values()).index(a['grid_descr']['f0.25_k50']['geo_ioi']) + 1,
                          best_minus_baseline=float(f"{min(v['geo_ioi'] for v in a['grid_descr'].values()) - a['best_head_no_evaluator']['ioi']:.1e}")),
    grid=dict(geo_ioi_range=[r3(min(v['geo_ioi'] for v in a['grid_descr'].values())), r3(max(v['geo_ioi'] for v in a['grid_descr'].values()))],
              auroc_diff_range=[r3(min(v['auroc_diff_mean'] for v in a['grid_descr'].values())), r3(max(v['auroc_diff_mean'] for v in a['grid_descr'].values()))]),
    tie_by_id={e: r3(v['ioi']) for e, v in a['evaluators_tie_by_id'].items()},
    best_head_no_evaluator={k: (r3(v) if isinstance(v, float) else v) for k, v in a['best_head_no_evaluator'].items()},
    any_head_correct_ood=r3(a['any_head_correct_ood']),
    pilot=dict(P1_delta=r3(pil['P1']['delta']), P3_delta=r3(pil['P3']['delta']), geo_ioi=r3(pil['evaluators']['GEO']['ioi']),
               agree_ioi=r3(pil['evaluators']['AGREE']['ioi'])),
    expectations=exp, brier=round(brier, 4), weight_bits={k: round(v, 2) for k, v in w.items()},
    power={k: pw[k]['power'] for k in ('P1', 'P3')},
    constants=dict(registration='1b43fe66', draft='5d62c897', council_lenses=52, kaggle_slug='neu-ocgeo-test', geo_f=0.25, geo_k=50,
                   boot=4000, false_level=0.005, series_false=0.01, expectation_probs=P, n_test=5669, n_pilot=2429,
                   literature=['1803.04765', '2509.19372', '2506.07962', '2605.23315'], errors_refs=[150, 152, 153], sum_threshold=100,
                   min_correct=min(min(v['id_correct'], v['ood_correct']) for v in a['method']['counts'].values()),
                   min_wrong=min(min(v['id_wrong'], v['ood_wrong']) for v in a['method']['counts'].values())))
json.dump(out, open(os.path.join(HERE, 'facts_ocgeo.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps({k: out[k] for k in ('verdict', 'evaluators', 'P1', 'P3', 'top10', 'no_twins', 'expectations', 'brier', 'weight_bits')}, ensure_ascii=False)[:3000])
