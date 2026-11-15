#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCREP-01: основа ожиданий PREREG §7 → expectations.json (до данных теста).
Предсказательное распределение разности на тесте по пилоту: нормальное, центр — точка пилота, разброс —
√(SE_теста² + SE_пилота²), где SE_пилота = SE_теста / √(n_OOD пилота / n_OOD теста) (power.json). Порог — z · SE_теста.
P(подтверждено) = P(Δ̂ < −z·SE), P(опровергнуто) = P(Δ̂ > z·SE), P(эффект x исключён) = P(Δ̂ − z·SE > x)."""
import json
import os
from math import erf, sqrt

HERE = os.path.dirname(os.path.abspath(__file__))
Phi = lambda z: 0.5 * (1 + erf(z / sqrt(2)))          # noqa: E731


def main():
    p = json.load(open(os.path.join(HERE, 'power.json'), encoding='utf-8'))
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
    json.dump(out, open(os.path.join(HERE, 'expectations.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == '__main__':
    main()
