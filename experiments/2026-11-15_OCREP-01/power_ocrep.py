#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCREP-01: мощность до прогона и решение по условию R3 → power.json. Основа — analysis_pilot.json.
Нормальное приближение, как в OCCOR-01 и OCMIX-01: SE теста = ширина ДИ 99 % пилота / (2 · 2,576) · √(n_OOD пилота / n_OOD теста);
эффект ужимается вдвое; мощность — Φ(|Δ|/2 / SE − z); вес — log₂(мощность / LEVEL); MDE при мощности 0,8 — (z + 0,8416) · SE.
Условие R3 (HYPOTHESIS, закреплено до пилота; совет 57): самообман верхушки AGREE на пилоте > 0,15 И мощность R3 при эффекте
вдвое ≥ 0,8 → r3_gate = True; иначе R3 снимается до регистрации и идёт описательно.
Описательно — мощность подтверждения R1 и R2 при эффектах прежних тестов (C-086, C-087) и при половине наименьшего из них.
Совет 58 (до регистрации): вердикт R1, R2 — по конъюнкции BC и процентильного ДИ. Поэтому главная мощность (conj) считается
с порогами по прогону цепочки на ответах пилота (pilot/analysis_test_rules_on_pilot.json, 10000 повторов): расстояние от точки
до границы — дальнее из BC и процентильного, умноженное на √(n_OOD пилота / n_OOD теста); разброс разности на тесте — SE
выше. Мощность в сторону знака пилота при эффекте вдвое — для прочтения «не проверено» (< 0,05) и веса; вес — log₂(мощность /
LEVEL), а при мощности не выше LEVEL — 0 (тест слабее своего ложного уровня опоры не даёт). Прежняя симметричная мощность
оставлена полями power и weight_bits_symmetric."""
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
                      power={'по пилоту': p_full, 'ужатый вдвое': p_half}, weight_bits_symmetric=log2(max(p_half, 1e-3) / R.LEVEL))
        out[k]['weight_bits'] = out[k]['weight_bits_symmetric']
    ch = json.load(open(os.path.join(HERE, 'pilot', 'analysis_test_rules_on_pilot.json'), encoding='utf-8'))
    for k in ('R1', 'R2'):
        c, se = ch[k], out[k]['se_test']
        dist = dict(lo_bc=(c['delta'] - c['ci'][0]) * scale, lo_pct=(c['delta'] - c['ci_percentile'][0]) * scale,
                    hi_bc=(c['ci'][1] - c['delta']) * scale, hi_pct=(c['ci_percentile'][1] - c['delta']) * scale)
        lo_d, hi_d = max(dist['lo_bc'], dist['lo_pct']), max(dist['hi_bc'], dist['hi_pct'])
        d = out[k]['delta_pilot']
        thr = lo_d if d > 0 else hi_d                    # в сторону знака пилота: «плюс» — опровергнуто, «минус» — подтверждено
        pf, ph = Phi((abs(d) - thr) / se), Phi((abs(d) / 2 - thr) / se)
        za = -zr                                         # z уровня 0,0025 (нижний хвост)
        out[k]['conj'] = dict(z0_pilot_chain=c['z0'], bc_quantiles=[Phi(2 * c['z0'] + za), Phi(2 * c['z0'] - za)], dist=dist, lower=lo_d, upper=hi_d,
                              power={'по пилоту': pf, 'ужатый вдвое': ph},
                              mde_confirm_power08=hi_d + 0.8416 * se, mde_refute_power08=lo_d + 0.8416 * se)
        out[k]['weight_bits'] = log2(ph / R.LEVEL) if ph > R.LEVEL else 0.0
        out[k]['reading_power'] = ph
    # Описательно (PREREG §6; вес и правила не меняет): мощность «подтверждено» при эффектах прежних тестов C-086 (R1) и C-087 (R2)
    # и при половине наименьшего — по конъюнкции (порог — дальняя верхняя граница); мощность «исключён» (оба ДИ, порог — дальняя
    # нижняя граница) при истинной разности 0 и при разности пилота. Числа эффектов — из run/analysis.json тех опытов.
    for k, pe in R.prior_effects().items():
        cj, se, d = out[k]['conj'], out[k]['se_test'], out[k]['delta_pilot']
        out[k]['power_prior_descr'] = {name: dict(effect=x, power=Phi((abs(x) - cj['upper']) / se), power_symmetric=Phi(abs(x) / se - zr))
                                       for name, x in pe.items()}
        out[k]['exclusion_power_descr'] = {name: {'при Δ = 0': Phi((-x - cj['lower']) / se), 'при Δ пилота': Phi((d - x - cj['lower']) / se)}
                                           for name, x in pe.items()}
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
