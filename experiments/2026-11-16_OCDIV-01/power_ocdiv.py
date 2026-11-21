#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-01: мощность правил на тесте по пилоту 2 и ожидания для tools/self_calibration.py → expect_ocdiv.json.
  python3 power_ocdiv.py [PILOT2.json] [OUT.json]
Модель «новая среда» (как в OCPOST-01): точка среды ~ N(μ, τ² + s²), μ и τ — по десяти средам пилота 2, s — ст. откл. повторов
среды, пересчитанное на тест по числу задач диапазона правила (ocdiv.agg_power). Правило выносится по среднему пяти сред,
интервал M4 — среднее ± z·s/√5. Для знаковых правил — ещё Монте-Карло с предохранителем «без одного диапазона». Оценка τ обрезана
по нулю, поэтому дана и мощность при τ = s (совет 64, п. 6); ожидания по правилам равенства и D3 — по ней."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ocdiv as V  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, 'gha_out/ocdiv_sum_pilot2/pilot2.json')
SEED_MC, N_MC, M = 7_990_000, 200_000, 5
P_METHOD = 0.95                                   # вероятность, что метод опыта сработает (извлечение, сборка, годность), по суждению


def mc_guard(mu, tau, s, m=M, z=V.P.Z, n=N_MC, seed=SEED_MC):
    """Знаковое правило с предохранителем: доли «подтверждено» (верх < 0) и «опровергнуто» (низ > 0), когда знак среднего
    сохраняется при исключении любой одной среды."""
    g = np.random.default_rng(seed)
    x = g.normal(mu, np.sqrt(tau ** 2 + s ** 2), size=(n, m))
    mean = x.mean(1)
    h = z * s / np.sqrt(m)
    loo = (x.sum(1, keepdims=True) - x) / (m - 1)
    holds = np.all(loo * mean[:, None] > 0, axis=1)
    return float(np.mean((mean + h < 0) & holds)), float(np.mean((mean - h > 0) & holds))


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else SRC
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'expect_ocdiv.json')
    r = json.load(open(src, encoding='utf-8'))
    rules = {'D1': r['power_d1']['d1'], 'D1 adj (описательно)': r['power_d1']['d1_adj'], **r['power']['rules']}
    kinds = {'D1': 'sign', 'D1 adj (описательно)': 'sign', **{k: v[1] for k, v in V.RULES_D.items()}}
    out = {}
    for k, e in rules.items():
        kind = kinds[k]
        row = dict(kind=kind, mu=e['mu'], tau=e['tau'], s_test=e['s_test'], n_pilot=e['n_pilot'], n_test=e['n_test'],
                   power_confirm=e['power_confirm'], power_refute=e['power_refute'])
        c_s, r_s = V.power_rule(kind, e['mu'], e['s_test'], e['s_test'], M)
        row.update(power_confirm_tau_s=c_s, power_refute_tau_s=r_s)
        if kind == 'sign':
            gc, gr = mc_guard(e['mu'], e['tau'], e['s_test'])
            row.update(power_confirm_guard=gc, power_refute_guard=gr)
        out[k] = row
    pdef = r['p_defined']['p_defined']
    X = [('E1', 'D1 опровергнуто (Q-нов − Q-py > 0: ошибки разнородной толпы совпадают чаще, чем у шести Pythia)',
          P_METHOD * out['D1']['power_refute_guard'], '0,95 × мощность «опровергнуто» с предохранителем; перенос на p = 2 не проверен'),
         ('E2', 'D2 подтверждено (wc CONF разнородной толпы < 0: C-090 вне семейства Pythia)',
          P_METHOD * out['D2']['power_confirm_guard'], '0,95 × мощность с предохранителем; перенос на p = 2 не проверен'),
         ('E3', 'D3 опровергнуто (калибровка FIXED-нов на ID переносится вне диапазона: C − T в полосе ±0,02)',
          P_METHOD * out['D3']['power_refute_tau_s'], '0,95 × мощность «внутри полосы» при τ = s'),
         ('E4', 'D3 подтверждено (не переносится: C − T вне полосы ±0,02)',
          P_METHOD * out['D3']['power_confirm_tau_s'], '0,95 × мощность «вне полосы» при τ = s'),
         ('E5', 'D4 подтверждено (wc POST разнородной толпы в полосе ±0,02: C-100 вне семейства Pythia)',
          P_METHOD * out['D4']['power_confirm_tau_s'], '0,95 × мощность при τ = s'),
         ('E6', 'N подтверждено (wc FIXED-нов в полосе ±0,02)', P_METHOD * out['N']['power_confirm_tau_s'], '0,95 × мощность при τ = s'),
         ('E7', 'опыт определён (годны не меньше 4 сред из 5, ревизии голов совпали)', P_METHOD * pdef,
          '0,95 × вероятность по пилоту (биномиальная модель проверки метода)'),
         ('E8', 'D3 не решено (интервал C − T FIXED-нов ни целиком в полосе ±0,02, ни целиком вне)',
          P_METHOD * (1 - out['D3']['power_refute_tau_s'] - out['D3']['power_confirm_tau_s']), '0,95 × (1 − мощность обоих исходов при τ = s); совет 66, п. 4')]
    trivial = {'E1', 'E2', 'E5', 'E6'}    # совет 66 (скептик): исход почти известен по пилоту — в калибровке считаются отдельно («(после пилота)»)
    res = dict(source=os.path.relpath(src, ROOT), m=M, z=V.P.Z, band=V.P.BAND, n_mc=N_MC, seed_mc=SEED_MC, p_method=P_METHOD,
               rules=out, p_defined=r['p_defined'], expect=[dict(id=a, text=b, p=round(c, 3), source=d, trivial=a in trivial) for a, b, c, d in X])
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for k, v in out.items():
        print(k, {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()})
    for e in res['expect']:
        print(e['id'], e['p'], e['text'])


if __name__ == '__main__':
    main()
