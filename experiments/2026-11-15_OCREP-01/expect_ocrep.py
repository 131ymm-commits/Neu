#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCREP-01: основа ожиданий PREREG §7 → expectations.json (до данных теста).
Предсказательное распределение разности на тесте по пилоту: нормальное, центр — точка пилота, разброс —
√(SE_теста² + SE_пилота²), где SE_пилота = SE_теста / √(n_OOD пилота / n_OOD теста) (power.json). Порог — z · SE_теста.
P(подтверждено) = P(Δ̂ < −z·SE), P(опровергнуто) = P(Δ̂ > z·SE), P(эффект x исключён) = P(Δ̂ − z·SE > x).
Второй вариант (bc) — границы как у ДИ BC правил на ответах пилота (pilot/analysis_test_rules_on_pilot.json, 10000 повторов):
расстояния от точки до нижней и до верхней границы, умноженные на √(n_OOD пилота / n_OOD теста). Он учитывает асимметрию BC
(z0 далеко от 0): P(подтверждено) = P(Δ̂ + верх < 0), P(опровергнуто) = P(Δ̂ − низ > 0), P(x исключён) = P(Δ̂ − низ > x).
Смесь (mix) — 0,7 · bc + 0,3 · нормальное: вердикт считается по BC, но z0 на тесте может быть другим."""
import json
import os
from math import erf, sqrt

HERE = os.path.dirname(os.path.abspath(__file__))
Phi = lambda z: 0.5 * (1 + erf(z / sqrt(2)))          # noqa: E731
W_BC = 0.7


def main():
    p = json.load(open(os.path.join(HERE, 'power.json'), encoding='utf-8'))
    ch = json.load(open(os.path.join(HERE, 'pilot', 'analysis_test_rules_on_pilot.json'), encoding='utf-8'))
    scale = sqrt(p['n_pilot_ood'] / p['n_test_ood'])
    z = p['z']
    out = dict(note='предсказательное распределение по пилоту; нормальное приближение; поправка к прежним тестам — в PREREG §7')
    for k in ('R1', 'R2'):
        s = p[k]
        d, se = s['delta_pilot'], s['se_test']
        sd = sqrt(se ** 2 + (se / scale) ** 2)
        th = z * se
        out[k] = dict(delta_pilot=d, se_test=se, se_pilot=se / scale, sd_pred=sd, threshold=th,
                      p_confirm=Phi((-th - d) / sd), p_refute=1 - Phi((th - d) / sd),
                      p_excluded={name: 1 - Phi((v['effect'] + th - d) / sd) for name, v in s['power_prior_descr'].items()})
        c = ch[k]
        lo_d, hi_d = (c['delta'] - c['ci'][0]) * scale, (c['ci'][1] - c['delta']) * scale
        out[k]['bc'] = dict(z0_pilot=c['z0'], lower_dist=lo_d, upper_dist=hi_d, p_confirm=Phi((-hi_d - d) / sd), p_refute=1 - Phi((lo_d - d) / sd),
                            p_excluded={name: 1 - Phi((v['effect'] + lo_d - d) / sd) for name, v in s['power_prior_descr'].items()})
        n_, b_ = out[k], out[k]['bc']
        out[k]['mix'] = dict(p_confirm=W_BC * b_['p_confirm'] + (1 - W_BC) * n_['p_confirm'], p_refute=W_BC * b_['p_refute'] + (1 - W_BC) * n_['p_refute'],
                             p_excluded={m: W_BC * b_['p_excluded'][m] + (1 - W_BC) * n_['p_excluded'][m] for m in n_['p_excluded']})
    json.dump(out, open(os.path.join(HERE, 'expectations.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == '__main__':
    main()
