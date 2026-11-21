#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCPOST-01: производные числа отчёта, которых нет в json счёта (чтобы ledger.py audit их находил). Сборка чисел, вердиктов не меняет.
  python3 facts_ocpost.py ANALYSIS.json TAIL.json OUT.json
Вес опоры — по PREREG §10: log₂(мощность / ложный уровень). Мощность — PREREG §6 (expect_ocpost.json): у P0–P2 — с предохранителем,
у P3 — при τ = s. Ложный уровень у P0–P2 — наибольшее из 0,0025 и верхней границы доли промахов M4 этой статистики по Т на нужной
стороне («подтверждено» — сверху, miss_high; «опровергнуто» — снизу, miss_low); у P3 — номинал (Т у P3 малоинформативна). Если описательная
проверка по группам из пяти миров даёт верхнюю границу больше — она записывается рядом. Т «опровергнуто» — вес 0. N и Т — 0 бит.
Опровержение даёт отрицательный вес: −log₂(мощность «опровергнуто» / ложный уровень)."""
import json
import os
import sys
from math import log2

import numpy as np

X = os.path.dirname(os.path.abspath(__file__))
LEVEL = 0.0025


def main(an_path, tail_path, dst):
    an = json.load(open(an_path, encoding='utf-8'))
    tl = json.load(open(tail_path, encoding='utf-8'))
    ex = json.load(open(os.path.join(X, 'expect_ocpost.json'), encoding='utf-8'))
    rp = ex['rules']
    power_c = {k: rp[k].get('power_confirm_guard', rp[k]['power_confirm_tau_s']) for k in ('P0', 'P1', 'P2')}
    power_c['P3'] = rp['P3']['power_confirm_tau_s']
    power_r = {k: rp[k].get('power_refute_guard', 0.0) for k in ('P0', 'P1', 'P2')}
    out = dict(source='PREREG-OCPOST-01 §6, §10 (регистрация 8ccae4a4)', tail_verdict=tl['verdict'], weights={}, false_level={})
    for k in ('P0', 'P1', 'P2', 'P3'):
        v = an['verdicts'][k]
        e = tl['stats'][k]
        g = tl.get('mean_of_5_descr', {}).get(k, {})
        if k == 'P3':
            fl, side = LEVEL, 'номинал (Т малоинформативна)'
        elif v == 'опровергнуто':
            fl, side = max(LEVEL, e['upper_low']), 'снизу (miss_low)'
        else:
            fl, side = max(LEVEL, e['upper_high']), 'сверху (miss_high)'
        grp = g.get('upper_low' if v == 'опровергнуто' else 'upper_high')
        out['false_level'][k] = dict(value=fl, side=side, tail_upper_low=e['upper_low'], tail_upper_high=e['upper_high'],
                                     groups_descr=grp, groups_larger=bool(grp is not None and grp > fl))
        if tl['verdict'] == 'опровергнуто' or v not in ('подтверждено', 'опровергнуто'):
            w = 0.0
        elif v == 'подтверждено':
            w = log2(power_c[k] / fl)
        else:
            w = -log2(max(power_r.get(k, 0.0), 1e-12) / fl) if power_r.get(k, 0.0) > 0 else 0.0
        out['weights'][k] = dict(bits=w, verdict=v, power=power_c[k] if v == 'подтверждено' else power_r.get(k))
    out['weights']['N'] = dict(bits=0.0, verdict=an['verdicts']['N'], note='служебное условие для P3 (PREREG §9, §10)')
    out['weights']['Т'] = dict(bits=0.0, verdict=tl['verdict'], note='проверка метода (PREREG §10)')
    # средние по средам для таблицы отчёта (точки — из analysis.json; здесь только сводка по средам)
    valid = an['method']['valid']
    out['by_env'] = {n: {k: an['envs'][n]['rules_env'][k]['point'] for k in ('P0', 'P1', 'P2', 'P3', 'N')} for n in valid}
    out['by_env_sd'] = {n: {k: an['envs'][n]['rules_env'][k]['sd'] for k in ('P0', 'P1', 'P2', 'P3', 'N')} for n in valid}
    out['sign_count'] = {k: dict(neg=int(sum(out['by_env'][n][k] < 0 for n in valid)), pos=int(sum(out['by_env'][n][k] > 0 for n in valid)), n=len(valid))
                         for k in ('P0', 'P1', 'P2')}
    out['in_band_count'] = {k: int(sum(abs(out['by_env'][n][k]) <= 0.02 for n in valid)) for k in ('P3', 'N')}
    # части ИОИ по оценщикам (среднее по годным средам; точки)
    parts = {}
    for e_ in ('CONF', 'POST-CV', 'ONE-BEST', 'FIXED', 'SHIFT'):
        parts[e_] = {q: float(np.mean([an['envs'][n]['point'][f'{q} {e_}'] for n in valid])) for q in ('T', 'C', 'ign', 'dec', 'ioi', 'brier')}
    out['parts_mean'] = parts
    out['one_best'] = {n: an['envs'][n]['extras']['one_best'] for n in valid}
    out['max_tail_rate'] = {k: max(tl['stats'][k]['rate_low'], tl['stats'][k]['rate_high']) for k in tl['stats']}
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(dict(weights=out['weights'], false_level=out['false_level']), ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(*sys.argv[1:4])
