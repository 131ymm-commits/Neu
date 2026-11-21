#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCCOR-01: мощность до прогона → power.json. Основа — разбор пилота (analysis_pilot.json: те же оценщики, вложенный
бутстреп, ничьи «поровну»).
Нормальное приближение: стандартная ошибка на тесте = ширина ДИ 99 % пилота / (2 · 2,576) · √(n_OOD пилота / n_OOD теста).
Эффект ужимается вдвое (урок № 152/154: правила и оценщики закреплены до пилота, но пилот один, и его эффект
переоценён). Мощность исхода — Φ(|Δ|/2 / SE − z), где z — квантиль уровня LEVEL на сторону.
Вес исхода, который даёт данные (заранее): log₂(мощность / LEVEL); вес отрицательного исхода — тот же по модулю, со знаком
минус (опровержение). P-значения не считаются; Монте-Карло нет — только нормальное приближение."""
import json
import os
import sys
from math import erf, log2, sqrt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_occor_test as R  # noqa: E402

Phi = lambda z: 0.5 * (1 + erf(z / sqrt(2)))          # noqa: E731


def z_of(level):
    lo, hi = 0.0, 10.0
    for _ in range(80):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if 1 - Phi(m) > level else (lo, m)
    return (lo + hi) / 2


def main(n_test_ood=None):
    a = json.load(open(os.path.join(HERE, 'analysis_pilot.json'), encoding='utf-8'))
    n_p = a['n_ood']
    n_t = n_test_ood or 3453                            # раскладка теста: occor_extract.py, SPLIT = 'test'
    scale = sqrt(n_p / n_t)
    z99, zr = 2.576, z_of(R.LEVEL)
    src = {'R1': a['full_delta']['LR-AGREE−AGREE'], 'R2': a['full_delta']['NB-AGREE−AGREE'], 'R3': a['full_delta']['LR-AGREE−NB-IND'],
           'R4': a['dose_contrast']['LR-AGREE']}
    out = dict(n_pilot_ood=n_p, n_test_ood=n_t, level=R.LEVEL, z=zr, series_false_level=4 * R.LEVEL,
               note='нормальное приближение по ДИ 99 % пилота; эффект ужат вдвое; для R4 стандартная ошибка — по закреплённым толпам пилота')
    for k, s in src.items():
        d, (lo, hi) = s['point'], s['ci99']
        se = (hi - lo) / (2 * z99) * scale
        p_full, p_half = Phi(abs(d) / se - zr), Phi(abs(d) / 2 / se - zr)
        out[k] = dict(delta_pilot=d, ci99_pilot=[lo, hi], se_test=se, expected_sign='минус' if d < 0 else 'плюс',
                      power={'по пилоту': p_full, 'ужатый вдвое': p_half}, weight_bits=log2(max(p_half, 1e-3) / R.LEVEL))
    json.dump(out, open(os.path.join(HERE, 'power.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == '__main__':
    main()
