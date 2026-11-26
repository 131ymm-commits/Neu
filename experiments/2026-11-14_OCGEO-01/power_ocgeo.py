#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCGEO-01: мощность до прогона → power.json (редакция после совета 52).
Основа — зарегистрированный анализ на данных пилота 1 (pilot1/analysis_test_rules_on_pilot.json: те же правила, что на тесте,
вложенный бутстреп, ничьи «поровну»). Нормальное приближение: стандартная ошибка на тесте = ширина ДИ 99 % пилота / (2·2,576) ×
√(n_OOD пилота / n_OOD теста). Мощность исхода — Φ(|Δ| / SE − 2,576).
Сценарии: «по пилоту» — Δ пилота; «осторожный» — Δ вдвое меньше.
ВНИМАНИЕ (совет 52, п. 6): модель мощности построена на том же пилоте, что породил утверждение P1, — по кругу; мощность
и вес — оценка сверху.
Ложный уровень каждого исхода — 0,005 (одна сторона ДИ 99 %); правил с весом два (P1, P3) — серия не выше 0,01.
Веса (заранее): log₂(мощность «осторожного» / 0,005) для исхода, который даёт данные; P2 — описательное, без веса.
Прежний расчёт (Монте-Карло с закреплённой калибровкой и argmax) — в истории git; заменён, потому что калибровка теперь
переподгоняется в каждом повторе."""
import json
import os
from math import erf, log2, sqrt

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
Z = 2.576
Phi = lambda z: 0.5 * (1 + erf(z / sqrt(2)))          # noqa: E731


def n_test_ood():
    pairs = [(a, b) for a in range(10, 100) for b in range(10, 100)]
    pairs = [p for p in pairs if p not in {(67, 68), (56, 67)}]      # пары подсказки (пилот 0)
    perm = np.random.default_rng(7_200_000).permutation(len(pairs))
    test = perm[int(round(0.3 * len(pairs))):]
    return int(sum(pairs[i][0] + pairs[i][1] >= 100 for i in test))


def main():
    a = json.load(open(os.path.join(HERE, 'pilot1', 'analysis_test_rules_on_pilot.json'), encoding='utf-8'))
    n_p, n_t = a['n_ood'], n_test_ood()
    scale = sqrt(n_p / n_t)
    out = dict(n_pilot_ood=n_p, n_test_ood=n_t, z=Z, false_level=0.005, series_false_level=0.01,
               note='нормальное приближение по ДИ 99 % зарегистрированного анализа на пилоте; модель по кругу — оценка сверху')
    for key, src in (('P1', a['P1']), ('P2_descr', a['P2_descr']), ('P3', a['P3'])):
        d, (lo, hi) = src['delta'], src['ci99']
        se = (hi - lo) / (2 * Z) * scale
        p_pilot, p_caut = Phi(abs(d) / se - Z), Phi(abs(d) / 2 / se - Z)
        if key == 'P1':
            outcome = 'опровергнуто' if d > 0 else 'подтверждено'
        elif key == 'P3':
            outcome = 'подтверждено' if d > 0 else 'опровергнуто'
        else:
            outcome = 'подтверждено' if d < 0 else 'опровергнуто'
        out[key] = dict(delta_pilot=d, ci99_pilot=[lo, hi], se_test=se, expected_outcome=outcome,
                        power={'по пилоту': p_pilot, 'осторожный': p_caut},
                        weight_bits=(log2(max(p_caut, 1e-3) / 0.005) if key != 'P2_descr' else 0.0))
    json.dump(out, open(os.path.join(HERE, 'power.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
