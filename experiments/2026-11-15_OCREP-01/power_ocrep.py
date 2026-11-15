#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCREP-01: мощность до прогона и решение по условию R3 → power.json. Основа — analysis_pilot.json.
Нормальное приближение, как в OCCOR-01 и OCMIX-01: SE теста = ширина ДИ 99 % пилота / (2 · 2,576) · √(n_OOD пилота / n_OOD теста);
эффект ужимается вдвое; мощность — Φ(|Δ|/2 / SE − z); вес — log₂(мощность / LEVEL); MDE при мощности 0,8 — (z + 0,8416) · SE.
Условие R3 (HYPOTHESIS, закреплено до пилота; совет 57): самообман верхушки AGREE на пилоте > 0,15 И мощность R3 при эффекте
вдвое ≥ 0,8 → r3_gate = True; иначе R3 снимается до регистрации и идёт описательно."""
import json
import os
import sys
from math import erf, log2, sqrt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_ocrep_test as R  # noqa: E402

Phi = lambda z: 0.5 * (1 + erf(z / sqrt(2)))          # noqa: E731
GATE_TOP, GATE_POWER = 0.15, 0.8


def gate(top, p_half):
    """Условие включения R3 (строго больше по верхушке, не меньше по мощности)."""
    return bool(top > GATE_TOP and p_half >= GATE_POWER)


def z_of(level):
    lo, hi = 0.0, 10.0
    for _ in range(80):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if 1 - Phi(m) > level else (lo, m)
    return (lo + hi) / 2


def main(n_test_ood=3431):
    a = json.load(open(os.path.join(HERE, 'analysis_pilot.json'), encoding='utf-8'))
    n_p, n_t = a['n_ood'], n_test_ood                   # раскладка теста: ocrep_extract.py, SPLIT = 'test' — 3431 задача OOD
    scale = sqrt(n_p / n_t)
    z99, zr = 2.576, z_of(R.LEVEL)
    out = dict(n_pilot_ood=n_p, n_test_ood=n_t, level=R.LEVEL, z=zr, note='нормальное приближение по ДИ 99 % пилота; эффект ужат вдвое')
    for k in ('R1', 'R2', 'R3'):
        s = a['deltas'][k]
        d, (lo, hi) = s['point'], s['ci99']
        se = (hi - lo) / (2 * z99) * scale
        p_full, p_half = Phi(abs(d) / se - zr), Phi(abs(d) / 2 / se - zr)
        out[k] = dict(delta_pilot=d, ci99_pilot=[lo, hi], se_test=se, expected_sign='минус' if d < 0 else 'плюс', mde_power08=(zr + 0.8416) * se,
                      power={'по пилоту': p_full, 'ужатый вдвое': p_half}, weight_bits=log2(max(p_half, 1e-3) / R.LEVEL))
    top = a['agree_top10_sel_deception']
    gate_ = gate(top, out['R3']['power']['ужатый вдвое'])
    out['r3_gate'] = dict(active=gate_, agree_top10_sel_deception_pilot=top, threshold_top=GATE_TOP, r3_power_half=out['R3']['power']['ужатый вдвое'],
                          threshold_power=GATE_POWER)
    out['series_false_level'] = R.LEVEL * (3 if gate_ else 2)
    json.dump(out, open(os.path.join(HERE, 'power.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == '__main__':
    main()
