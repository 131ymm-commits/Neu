#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCSHIFT-01: разбор пилота → OUT_DIR/analysis_pilot.json. python3 pilot_ocshift.py PILOT_DIR OUT_DIR
По HYPOTHESIS пилот даёт только две вещи, и только они считаются:
  1. Цепочка: две видеокарты отработали; блок сверки совпал с выводом пилота OCREP-01 (ответы и logp); время по головам
     и прогноз времени теста.
  2. Прогноз проверки метода: точность голов на свежих диапазонах (подсказка пилота, 300 задач на диапазон) и ожидаемое
     число верных и неверных ответов в среде теста (порог 20; запас — 30).
Сравнения оценщиков на пилоте не считаются."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['OCSHIFT_IMPORT_ONLY'] = '1'
sys.path.insert(0, HERE)
import ocshift_extract as X  # noqa: E402
import analyze_ocshift as S  # noqa: E402

Q = S.Q


def main(pilot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    d, envs = S.load_new(pilot_dir)
    test = [e for e in X.environments('test') if e['kind'] == 'test']
    n_test = {x: dict(id=float(np.mean([sum(p['range'] == 'ID' for p in e['problems']) for e in test if e['X'] == x])),
                      ood=float(np.mean([sum(p['range'] == 'OOD' for p in e['problems']) for e in test if e['X'] == x]))) for x in X.RANGES}
    n_prob = dict(pilot=int(sum(len(e['problems']) for e in d['envs'])), test=int(sum(len(e['problems']) for e in X.environments('test'))))
    res = dict(info=d['info'], seconds=d['seconds'], n_problems=n_prob,
               head_errors=[f"{h['model']}@{h['revision']}: {h['error']}" for h in d['heads'] if 'error' in h],
               first_errors=[f"{h['model']}@{h['revision']}: {h['first_error']}" for h in d['heads'] if h.get('first_error')],
               check=S.check_block(envs), heads={}, envs={})
    scale = n_prob['test'] / n_prob['pilot']
    wsec = {}
    for h in d['heads']:
        if 'cols' not in h:
            continue
        inf = float(sum(h['seconds_env'].values()))
        res['heads'][Q.label(h)] = dict(worker=h['worker'], where=h['where'], seconds=h['seconds'], inference=inf, load=h['seconds'] - inf,
                                        forecast_test=(h['seconds'] - inf) + inf * scale)
        wsec.setdefault(str(h['worker']), 0.0)
        wsec[str(h['worker'])] += (h['seconds'] - inf) + inf * scale
    res['forecast_test_seconds'] = dict(by_worker=wsec, wall=max(wsec.values()) if wsec else None, scale=scale)
    worst = {}
    for name, e in envs.items():
        if e['meta'].get('kind') != 'pilot':
            continue
        ans, corr, rid, logp = Q.arrays(dict(problems=e['problems']), e['heads'])
        x = e['meta']['X']
        r = dict(X=x, prompt_head=e['meta']['prompt_head'], n_id=int(rid.sum()), n_ood=int((~rid).sum()), heads={})
        for k, h in enumerate(e['heads']):
            a_id, a_ood = float(corr[k][rid].mean()), float(corr[k][~rid].mean())
            exp = dict(id_correct=a_id * n_test[x]['id'], id_wrong=(1 - a_id) * n_test[x]['id'],
                       ood_correct=a_ood * n_test[x]['ood'], ood_wrong=(1 - a_ood) * n_test[x]['ood'])
            lo = min(exp.values())
            r['heads'][Q.label(h)] = dict(acc_id=a_id, acc_ood=a_ood, none_frac=float(np.mean([v is None for v in ans[k]])),
                                          expected_min_count=lo, forecast_ok=bool(lo >= 20), forecast_margin=bool(lo >= 30))
            worst[Q.label(h)] = min(worst.get(Q.label(h), 1e9), lo)
        r['forecast_pass'] = int(sum(v['forecast_ok'] for v in r['heads'].values()))
        r['best_head_id'] = max(r['heads'], key=lambda q: r['heads'][q]['acc_id'])
        r['best_head_ood'] = max(r['heads'], key=lambda q: r['heads'][q]['acc_ood'])
        res['envs'][name] = r
    res['forecast'] = dict(min_pass=min(v['forecast_pass'] for v in res['envs'].values()), worst_expected_count=worst,
                           ranges_below_6=int(sum(v['forecast_pass'] < 6 for v in res['envs'].values())))
    json.dump(res, open(os.path.join(out_dir, 'analysis_pilot.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    c = res['check']
    print('площадка:', res['info'])
    print('ошибки голов:', res['head_errors'], '| первые ошибки (до повтора):', res['first_errors'])
    print(f"сверка цепочки: ответы равны — {c['answers_equal']}; наибольшее расхождение logp — {c['max_abs_dlogp']:.3g}; голов {c['n_heads']}")
    for hn, v in c['heads'].items():
        print('   ', hn, v)
    print('время, с:', res['seconds'], '| по головам:', {k: (round(v['seconds'], 1), 'W%d' % v['worker']) for k, v in res['heads'].items()})
    print('прогноз времени теста, с:', {k: round(v) for k, v in wsec.items()}, '→', round(res['forecast_test_seconds']['wall'] or 0))
    for name, r in res['envs'].items():
        print(f"{name}: ID {r['n_id']}, OOD {r['n_ood']}; пройдут проверку метода по прогнозу: {r['forecast_pass']} из {len(r['heads'])}; "
              f"лучшая на ID — {r['best_head_id']}, лучшая на OOD — {r['best_head_ood']}")
        for hn, v in r['heads'].items():
            print(f"    {hn:26s} ID {v['acc_id']:.3f} OOD {v['acc_ood']:.3f} | наименьшее ожидаемое число {v['expected_min_count']:.0f} "
                  f"{'' if v['forecast_ok'] else '— НЕ ПРОЙДЁТ'}")
    print('итог прогноза:', res['forecast'])
    return res


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
