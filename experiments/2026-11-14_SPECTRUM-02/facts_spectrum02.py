#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-02: числа отчёта из run/analysis.json, power.json и results.json → facts_spectrum02.json. Ожидания §7 ставит код."""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
r = json.load(open(os.path.join(HERE, 'run', 'analysis.json'), encoding='utf-8'))
pw = json.load(open(os.path.join(HERE, 'power.json'), encoding='utf-8'))
secs = json.load(open(os.path.join(HERE, 'run', 'results.json'), encoding='utf-8'))['seconds']
r3 = lambda x: None if x is None else round(float(x), 3)          # noqa: E731
rng = lambda v: [r3(min(v)), r3(max(v))]                           # noqa: E731
ci = lambda v: [r3(x) for x in v]                                  # noqa: E731
p1, p2, p3, p4, sh, mm = r['P1'], r['P2'], r['P3'], r['P4'], r['shape'], r['method']
ta = r['descr']['t_align']
phase = r['phase_at_t_align']
exp = {'E1': int(p1['verdict'] == 'подтверждено'), 'E2': int(p2['verdict'] == 'подтверждено'),
       'E3': int(p3['verdict'] == 'подтверждено'), 'E4': int(p4['verdict'] == 'подтверждено'),
       'E5': int(not r['verdict'].startswith('не определено')), 'E6': int(p4['A']['ci99'][1] < 0.40),
       'E7': int(sh['verdict'] == 'не решено'), 'E8': int(all(v['loss_frac'] < 0.01 for v in phase.values()))}
P = {'E1': 0.97, 'E2': 0.8, 'E3': 0.8, 'E4': 0.75, 'E5': 0.9, 'E6': 0.85, 'E7': 0.85, 'E8': 0.95}
brier = sum((P[k] - v) ** 2 for k, v in exp.items()) / len(exp)
wb = pw['weights_bits']
bits = {'P1': wb['P1']['confirm'] if p1['verdict'] == 'подтверждено' else (wb['P1']['refute'] if p1['verdict'] == 'опровергнуто' else 0.0),
        'P2': wb['P2']['confirm'] if p2['verdict'] == 'подтверждено' else (wb['P2']['refute'] if p2['verdict'] == 'опровергнуто' else 0.0),
        'P4': 0.0}
diff_sh = [h - l for h, l in zip(sh['delta_high'], sh['delta_low']) if h is not None and l is not None]
out = dict(
    verdict=r['verdict'], verdicts=r['verdicts'], blocks=r['blocks'], groups=len(r['measures']), need=r['need'],
    P1=dict(k=p1['k'], k_rev=p1['k_rev'], median_ratio=r3(p1['median_ratio']), ci=ci(p1['ci95']), ratio_range=rng(p1['ratio_A0_A1'])),
    P2=dict(k=p2['k'], k_rev=p2['k_rev'], median_ratio=r3(p2['median_ratio']), ci=ci(p2['ci95']), ratio_range=rng(p2['ratio_A1_AB1'])),
    P3=dict(k=p3['k'], k_rev=p3['k_rev'], median_alpha_A=r3(p3['median_alpha_A']), ci_alpha_A=ci(p3['ci95_alpha_A']),
            median_alpha_AB=r3(p3['median_alpha_AB']), ci_alpha_AB=ci(p3['ci95_alpha_AB']),
            median_diff=r3(p3['median_diff']), ci_diff=ci(p3['ci95_diff']), diff_range=rng(p3['diff'])),
    P4=dict(alpha_AB=r3(p4['AB']['alpha']), ci99_AB=ci(p4['AB']['ci99']), alpha_A=r3(p4['A']['alpha']), ci99_A=ci(p4['A']['ci99'])),
    shape=dict(k_mult=sh['k_mult'], k_signal=sh['k_signal'], median_delta_low=r3(sh['median_delta_low']),
               median_delta_high=r3(sh['median_delta_high']), ci_median_diff=ci(sh['ci95_median_diff']),
               median_diff=r3(np.median(diff_sh)), verdict=sh['verdict']),
    common_threshold=r['common_threshold']['P2'] | {'P3': r['common_threshold']['P3']},
    skeptic_AB1_lt_A1B23=r['descr_skeptic_AB1_vs_A1B23'],
    phase_max=dict(loss_frac=r3(max(v['loss_frac'] for v in phase.values())), norm_S=r3(max(v['norm_S'] for v in phase.values())),
                   norm_O=r3(max(v['norm_O'] for v in phase.values()))),
    method=dict(d_cka_min=r3(mm['d_cka_min']), sym_median=r3(mm['sym_median']), sym_ci=ci(mm['sym_ci95']), sym_range=rng(mm['sym_ratio_B1_A1']),
                lam_ratio_max_dev=round(mm['lam_ratio_max_dev'], 4), lam_monotone=mm['lam_monotone'],
                perm_gap_min=r3(r['descr']['perm_vs_init_min_gap'])),
    t_align={c: dict(range=rng(v), median=r3(np.median(v))) for c, v in ta.items()},
    lam_max_median={c: r3(np.median(v)) for c, v in r['descr']['lam_max'].items()},
    alpha_behav_self_A=r3(r['descr']['median_alpha_behav_self_A']),
    expectations=exp, brier=round(brier, 4), weight_bits={k: round(v, 2) for k, v in bits.items()},
    pilot=dict(alpha_A_pooled=r3(json.load(open(os.path.join(HERE, 'pilot', 'pilot_6_analysis.json'), encoding='utf-8'))['P4']['A']['alpha'])),
    constants=dict(registration='d04db806', draft='b37180aa', council_lenses=50, gha_run=43570576546, run_seconds=round(secs),
                   literature=['2610.29864', '2111.00034'], probe_points=4000,
                   n_blocks=30, k_sign=23, band=[round(1 / 3, 3), round(2 / 3, 3)], ci_p4=99, expectation_probs=P,
                   false_sign=r3(pw['false_level']['P1']), series_false=round(pw['series_false_level_weighted'], 4)))
json.dump(out, open(os.path.join(HERE, 'facts_spectrum02.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps({k: out[k] for k in ('verdict', 'P1', 'P2', 'P3', 'P4', 'shape', 'phase_max', 'method', 'expectations', 'brier', 'weight_bits')},
                 ensure_ascii=False, indent=0)[:3500])
