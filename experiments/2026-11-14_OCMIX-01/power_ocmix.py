#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCMIX-01: мощность до прогона → power.json. Основа — разбор пилота (analysis_pilot.json: те же оценщики, вложенный
бутстреп, ничьи «поровну», верхушка top10_sel). Нормальное приближение, как в OCCOR-01: стандартная ошибка на тесте =
ширина ДИ 99 % пилота / (2 · 2,576) · √(n_OOD пилота / n_OOD теста); верхушка — 10 % задач OOD, поэтому масштаб тот же.
Эффект ужимается вдвое. Мощность исхода — Φ(|Δ|/2 / SE − z), где z — квантиль уровня LEVEL на сторону.
Вес исхода, который даёт данные (заранее): log₂(мощность / LEVEL); опровержение — тот же вес со знаком минус."""
import json
import os
import sys
from math import erf, log2, sqrt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_ocmix_test as R  # noqa: E402

Phi = lambda z: 0.5 * (1 + erf(z / sqrt(2)))          # noqa: E731


def z_of(level):
    lo, hi = 0.0, 10.0
    for _ in range(80):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if 1 - Phi(m) > level else (lo, m)
    return (lo + hi) / 2


def main(n_test_ood=3409):
    a = json.load(open(os.path.join(HERE, 'analysis_pilot.json'), encoding='utf-8'))
    n_p, n_t = a['n_ood'], n_test_ood                   # раскладка теста: ocmix_extract.py, SPLIT = 'test' — 3409 задач OOD
    scale = sqrt(n_p / n_t)
    z99, zr = 2.576, z_of(R.LEVEL)
    out = dict(n_pilot_ood=n_p, n_test_ood=n_t, level=R.LEVEL, z=zr, series_false_level=3 * R.LEVEL,
               note='нормальное приближение по ДИ 99 % пилота (процентильный); эффект ужат вдвое; mde_power08 — минимальный обнаружимый эффект при мощности 0,8 (совет 56, описательно)')
    for k, src in (('R1', 'H1'), ('R2', 'H2'), ('R3', 'H3')):
        s = a['deltas'][src]
        d, (lo, hi) = s['point'], s['ci99']
        se = (hi - lo) / (2 * z99) * scale
        p_full, p_half = Phi(abs(d) / se - zr), Phi(abs(d) / 2 / se - zr)
        out[k] = dict(delta_pilot=d, ci99_pilot=[lo, hi], se_test=se, expected_sign='минус' if d < 0 else 'плюс', mde_power08=(zr + 0.8416) * se,
                      power={'по пилоту': p_full, 'ужатый вдвое': p_half}, weight_bits=log2(max(p_half, 1e-3) / R.LEVEL))
    json.dump(out, open(os.path.join(HERE, 'power.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == '__main__':
    main()
