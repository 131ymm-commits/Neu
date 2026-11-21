#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-01: числа отчёта из run/analysis.json и power.json → facts_spectrum01.json. Ожидания §7 ставит код."""
import json, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
r = json.load(open(os.path.join(HERE, 'run', 'analysis.json'), encoding='utf-8'))
pw = json.load(open(os.path.join(HERE, 'power.json'), encoding='utf-8'))
r3 = lambda x: None if x is None else round(float(x), 3)
med = lambda v: r3(np.median(v))
M = r['measures']
sel = lambda rg, q, nz, ex: [m for m in M if m['regime'] == rg and m['q'] == q and m['d_nuis'] == nz and m['extra'] == ex]
rich_p3 = sel('rich', 1.0, 52, 0) + sel('rich', 0.0, 52, 2)
cells = {}
for rg in ('rich', 'lazy'):
    for q in (1.0, 0.0):
        ms = sel(rg, q, 52, 0)
        cells[f'{rg}_q{int(q)}'] = dict(cka0=med([m['cka0'] for m in ms]), ckaT=med([m['ckaT'] for m in ms]), d_cka=med([m['d_cka'] for m in ms]),
                                        mknn0=med([m['mknn0'] for m in ms]), mknnT=med([m['mknnT'] for m in ms]),
                                        behavT=med([m['behavT'] for m in ms]), r2T=med([m['r2T'] for m in ms]))
ms = sel('rich', 0.0, 52, 2)
cells['rich_q0_d64'] = dict(cka0=med([m['cka0'] for m in ms]), ckaT=med([m['ckaT'] for m in ms]), mknnT=med([m['mknnT'] for m in ms]),
                            behavT=med([m['behavT'] for m in ms]))
p3, p62 = r['P3'], r['P3_q0_d62']
exp = {'E1': int(p3['verdict'] == 'подтверждено'), 'E2': int(p3['verdict'] != 'опровергнуто'),
       'E3': int(r['P1a']['ok'] and r['P1b']['ok'] and r['P2']['ok']), 'E4': int(r['lambda_S_max_q1'] == r['blocks']),
       'E5': int(all(m['t_align'] is not None and m['t_align'] < m['t_half_obj'][0] for m in rich_p3)),
       'E6': int(p62['median_ratio'] > p3['median_ratio'])}
P = {'E1': 0.75, 'E2': 0.95, 'E3': 0.95, 'E4': 0.95, 'E5': 0.95, 'E6': 0.7}
brier = sum((P[k] - v) ** 2 for k, v in exp.items()) / len(exp)
w = pw['weights_bits']['confirm_P3'] if p3['verdict'] == 'подтверждено' else (pw['weights_bits']['refute_P3'] if p3['verdict'] == 'опровергнуто' else 0.0)
out = dict(verdict=r['verdict'], P3=dict(t1_range=[r3(min(p3['t_align_q1'])), r3(max(p3['t_align_q1']))],
                                         t0_range=[r3(min(p3['t_align_q0'])), r3(max(p3['t_align_q0']))],
                                         ratios=[r3(x) for x in p3['ratios']], ratio_range=[r3(min(p3['ratios'])), r3(max(p3['ratios']))],
                                         median_ratio=r3(p3['median_ratio']), ci_median_ratio=[r3(x) for x in p3['ci95_median_ratio']],
                                         theory_range=[r3(min(p3['theory'])), r3(max(p3['theory']))], rel=[r3(x) for x in p3['rel']],
                                         rel_range=[r3(min(p3['rel'])), r3(max(p3['rel']))], median_rel=r3(p3['median_rel']),
                                         ci_median_rel=[r3(x) for x in p3['ci95_median_rel']], dev=r3(p3['dev']), k=p3['k'], k_rev=p3['k_rev'],
                                         n_defined=p3['n_defined'], secondary=p3['secondary_interval_ok'], verdict=p3['verdict']),
           P3_d62=dict(median_ratio=r3(p62['median_ratio']), ci_median_ratio=[r3(x) for x in p62['ci95_median_ratio']],
                       median_rel=r3(p62['median_rel']), ci_median_rel=[r3(x) for x in p62['ci95_median_rel']], k=p62['k'], verdict=p62['verdict']),
           P1a=dict(k=r['P1a']['k'], median=r3(r['P1a']['median']), ci=[r3(x) for x in r['P1a']['ci95_median']], min=r3(min(r['P1a']['diffs']))),
           P1b=dict(k=r['P1b']['k'], median=r3(r['P1b']['median']), ci=[r3(x) for x in r['P1b']['ci95_median']], min=r3(min(r['P1b']['diffs']))),
           P2=dict(k=r['P2']['k'], behav_range=[r3(min(r['P2']['behav'])), r3(max(r['P2']['behav']))],
                   d_cka_range=[r3(min(r['P2']['d_cka'])), r3(max(r['P2']['d_cka']))], d_cka_max=r3(max(r['P2']['d_cka_max'])),
                   traj_median={k: r3(np.median([t[k] for t in r['P2']['d_cka_traj']])) for k in r['P2']['d_cka_traj'][0]}),
           lambda_S_max_q1=r['lambda_S_max_q1'], argmax_q0={k: r['lambda_argmax_q0'].count(k) for k in ('S', 'O', 'B')},
           sweep={k: dict(cka0=med(v['cka0']), ckaT=med(v['ckaT']), d_cka=med(v['d_cka']), mknn0=med(v['mknn0']), mknnT=med(v['mknnT']))
                  for k, v in r['descr']['sweep'].items()},
           perm=dict(mean_range=[round(min(m['perm_mean'] for m in M), 4), round(max(m['perm_mean'] for m in M), 4)],
                     max=round(max(m['perm_max'] for m in M), 4), min_gap=r3(r['descr']['perm_vs_init_min_gap'])),
           t_align_over_t_half=[r3(min(m['t_align'] / m['t_half_obj'][0] for m in rich_p3)), r3(max(m['t_align'] / m['t_half_obj'][0] for m in rich_p3))],
           t_half_self=dict(q1=sorted({m['t_half_obj'][0] for m in sel('rich', 1.0, 52, 0)}), q0_d64=sorted({m['t_half_obj'][0] for m in ms})),
           t_align_at0_any=r['descr']['t_align_at0_any'], cells=cells, expectations=exp, brier=round(brier, 4),
           weight_bits=round(w, 2), power=pw, groups=len(M), blocks=r['blocks'],
           posthoc_exponent=dict(note='пост-хок по совету 49, вердикт не меняет: α = ln(медиана отношения)/ln(медиана теории²)',
                                 alpha=r3(np.log(p3['median_ratio']) / np.log(np.median(p3['theory']) ** 2)),
                                 alpha_from_ci=[r3(np.log(x) / np.log(np.median(p3['theory']) ** 2)) for x in p3['ci95_median_ratio']]),
           constants=dict(registration='2e0295ca', draft='03015542', literature=['2111.00034', '2610.29864', '2409.14623'],
                          probe_points=4000, widths=[32, 48, 64, 96], tol_ok=0.10, tol_bad=0.25, ratio_interval=[1.05, 1.40],
                          expectation_probs=P, run_seconds=1869))
json.dump(out, open(os.path.join(HERE, 'facts_spectrum01.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps({k: out[k] for k in ('verdict', 'P3', 'expectations', 'brier', 'weight_bits', 'cells')}, ensure_ascii=False)[:2500])
