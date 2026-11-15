#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCSHIFT-01: производные числа для отчёта → run/facts_ocshift.json (чтобы ledger.py audit находил каждое число отчёта).
  python3 facts_ocshift.py [ANALYSIS.json]   (по умолчанию gha_out/ocshift_test/analysis.json)
Источники — анализ теста (GitHub Actions), gha_out/ocshift_chain/power.json, gha_out/ocshift_pilot/analysis_pilot.json,
журнал Kaggle (run/out/kaggle_log.json), разбор трёх готовых сдвигов (gha_out/ocshift_explore).
Написан до данных теста; проверен на сухом прогоне (заглушки). Это сборка чисел, вердиктов не меняет."""
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
J = lambda p: json.load(open(p if os.path.isabs(p) else os.path.join(ROOT, p), encoding='utf-8'))  # noqa: E731
EV = ('AGREE', 'NB-AGREE', 'LR-AGREE', 'NB-IND', 'FAM-AGREE', 'CONF', 'VETO', 'MIX-LR')
EXPECT = dict(E1=0.45, E2=0.08, E3=0.93, E4=0.12, E5=0.30, E6=0.55, E7=0.90, E8=0.45)       # вероятности — копия таблицы PREREG §7


def main(src='gha_out/ocshift_test/analysis.json', dst=None):
    r = J(src)
    pw = J('gha_out/ocshift_chain/power.json')
    V = r['method']['valid']
    E = r['envs']
    out = dict(source=src, n_envs=r['method']['n_envs'], n_valid=r['method']['n_valid'])
    out['n_problems'] = dict(id=int(sum(E[n]['n_id'] for n in E)), ood=int(sum(E[n]['n_ood'] for n in E)))
    out['n_problems']['all'] = out['n_problems']['id'] + out['n_problems']['ood']
    out['crowd_size'] = {n: len(E[n]['crowd']) for n in E}
    out['crowd_size_range'] = dict(min=min(out['crowd_size'].values()), max=max(out['crowd_size'].values()))
    out['excluded_heads'] = {n: [h for h, v in E[n]['method'].items() if not v['ok']] for n in E}
    per = {}
    for n in V:
        p, x = E[n]['point'], E[n]['extras']
        best = min(EV, key=lambda e: p[f'ioi {e}'])
        per[n] = dict(one_best=x['one_best']['head'], one_best_is_best_ood=bool(x['one_best']['head'] == x['one_best']['best_ood_head']),
                      best_ood_head=x['one_best']['best_ood_head'], best_ood_acc=x['one_best']['best_ood_acc'],
                      T_one=p['T ONE-BEST'], C_one=p['C ONE-BEST'], dec_one=p['C ONE-BEST'] - p['T ONE-BEST'], ioi_one=p['ioi ONE-BEST'],
                      best8=best, ioi_best8=p[f'ioi {best}'], T_best8=p[f'T {best}'], oracle=x['oracle']['ood'],
                      T_range8=[min(p[f'T {e}'] for e in EV), max(p[f'T {e}'] for e in EV)],
                      one_beats_min8=bool(p['ioi ONE-BEST'] < p['ioi MIN8']), one_beats_lr=bool(p['ioi ONE-BEST'] < p['ioi LR-AGREE']),
                      one_beats_conf=bool(p['ioi ONE-BEST'] < p['ioi CONF']), conf_beats_lr=bool(p['ioi CONF'] < p['ioi LR-AGREE']))
    out['per_env'] = per
    out['counts'] = {k: int(sum(v[k] for v in per.values())) for k in ('one_beats_min8', 'one_beats_lr', 'one_beats_conf', 'conf_beats_lr', 'one_best_is_best_ood')}
    heads = {}
    for v in per.values():
        heads[v['one_best']] = heads.get(v['one_best'], 0) + 1
    out['one_best_heads'] = heads
    best8 = {}
    for v in per.values():
        best8[v['best8']] = best8.get(v['best8'], 0) + 1
    out['best8_counts'] = best8
    names = list(EV) + ['ONE-BEST', 'ONE-BEST+MIN', 'FUSE-MIN', 'POST-IN CONF', 'POST-IN LR-AGREE']
    out['mean'] = {e: {k: float(np.mean([E[n]['point'][f'{k} {e}'] for n in V])) for k in ('T', 'C', 'ioi', 'brier')} for e in names}
    for e in names:
        out['mean'][e]['dec'] = out['mean'][e]['C'] - out['mean'][e]['T']
    out['mean']['MIN8'] = dict(ioi=float(np.mean([E[n]['point']['ioi MIN8'] for n in V])), brier=float(np.mean([E[n]['point']['brier MIN8'] for n in V])))
    out['mean_oracle'] = float(np.mean([per[n]['oracle'] for n in V]))
    out['mean_best_ood_acc'] = float(np.mean([per[n]['best_ood_acc'] for n in V]))
    wc = {e: float(np.mean([E[n]['extras']['evaluators'][e]['id_crossfit']['dec'] for n in V])) for e in EV}
    out['selection_deception'] = dict(id_crossfit=wc, ood={e: out['mean'][e]['dec'] for e in EV},
                                      share_on_id={e: (wc[e] / out['mean'][e]['dec'] if out['mean'][e]['dec'] > 0 else None) for e in EV},
                                      one_best_id=float(-np.mean([E[n]['point']['wc ONE-BEST'] for n in V])),
                                      conf_id_rule=float(-np.mean([E[n]['point']['wc CONF'] for n in V])))
    out['switch'] = {e: {k: float(np.mean([E[n]['extras']['evaluators'][e]['vs_one_best'][k] for n in V]))
                         for k in ('switch', 'T_selected_on_switch', 'T_one_best_on_switch')} for e in ('LR-AGREE', 'CONF', 'AGREE')}
    out['post_cv'] = {e: dict(ioi=float(np.mean([E[n]['extras']['evaluators'][e]['post_cv']['ioi'] for n in V])),
                              brier=float(np.mean([E[n]['extras']['evaluators'][e]['post_cv']['brier'] for n in V]))) for e in ('CONF', 'VETO', 'LR-AGREE')}
    out['top10'] = dict({e: float(np.mean([E[n]['extras']['evaluators'][e]['top10']['deception'] for n in V])) for e in EV},
                        **{'ONE-BEST': float(np.mean([E[n]['extras']['one_best_top10']['deception'] for n in V]))})
    wb = [n for n in V if 'without_best' in E[n]['extras']]
    if wb:
        out['without_best'] = dict(n=len(wb), ioi_one_best_of_rest=float(np.mean([E[n]['extras']['without_best']['ioi ONE-BEST'] for n in wb])),
                                   ioi_min8=float(np.mean([E[n]['extras']['without_best']['ioi MIN8'] for n in wb])),
                                   ioi_lr=float(np.mean([E[n]['extras']['without_best']['ioi LR-AGREE'] for n in wb])))
    out['rule_ci_coverage'] = 1 - 2 * r['level']
    nd = [k for k in r if k.startswith('descr_')]
    out['descr_count'] = len(nd)
    out['descr_family_level_bonferroni'] = len(nd) * 2 * r['descr_level']
    out['power'] = {k: dict(reading=pw[k]['reading_power'], weight_bits=pw[k]['weight_bits']) for k in ('R1', 'R2', 'R3', 'R4')}
    base = float(np.log2(0.54 / 0.46))
    out['support_bits'] = dict(base_hypothesis_neu=base)
    out['analysis_seconds'] = r.get('seconds')
    kl = os.path.join(HERE, 'run', 'out', 'kaggle_log.json')
    if os.path.isfile(kl):
        m = [re.search(r'\[\s*([\d.]+)\s*с\]\s*готово', e['data']) for e in json.load(open(kl, encoding='utf-8')) if e['stream_name'] == 'stdout']
        m = [x for x in m if x]
        if m:
            out['extraction_seconds'] = float(m[-1].group(1))
    oc = dict(E1=int(r['verdicts']['R1'] == 'подтверждено'), E2=int(r['verdicts']['R1'] == 'опровергнуто'), E3=int(r['verdicts']['R2'] == 'подтверждено'),
              E4=int(r['verdicts']['R3'] == 'подтверждено'), E5=int(r['verdicts']['R3'] == 'опровергнуто'), E6=int(r['verdicts']['R4'] == 'подтверждено'),
              E7=int(r['method']['ok']), E8=int(heads.get('pythia-2.8b-deduped', 0) >= 8))
    out['expectations_outcome'] = oc
    out['expectations_prereg'] = dict(source='PREREG-OCSHIFT-01 §7 (копия таблицы)', **EXPECT)
    out['brier_ocshift'] = float(np.mean([(EXPECT[k] - oc[k]) ** 2 for k in oc]))
    dst = dst or os.path.join(HERE, 'run', 'facts_ocshift.json')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1)[:6000])
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0] if a else 'gha_out/ocshift_test/analysis.json', a[1] if len(a) > 1 else None)
