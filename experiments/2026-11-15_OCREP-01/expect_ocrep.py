#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCREP-01: основа ожиданий PREREG §7 → expectations.json (до данных теста).
Предсказательное распределение разности на тесте по пилоту: нормальное, центр — точка пилота, разброс —
√(SE_теста² + SE_пилота²), где SE_пилота = SE_теста / √(n_OOD пилота / n_OOD теста) (power.json).
Три расчёта:
  normal — порог z · SE теста с обеих сторон (бутстреп без смещения, z0 = 0);
  conj   — правило совета 58 (вывод — только если его дают и BC, и процентильный ДИ): порог — дальняя из границ BC и
           процентильной по прогону цепочки на ответах пилота, умноженная на √(n_OOD пилота / n_OOD теста) (power.json: conj);
  mix    — 0,7 · conj + 0,3 · normal: z0 на тесте может быть другим.
P(подтверждено) = P(Δ̂ + верх < 0), P(опровергнуто) = P(Δ̂ − низ > 0), P(x исключён, оба ДИ) = P(Δ̂ − низ > x);
P(«не решено (только BC)», сторона подтверждения) = P(−верх ≤ Δ̂ < −верх_BC), если верх_BC < верх (иначе 0)."""
import json
import os
from math import erf, sqrt

HERE = os.path.dirname(os.path.abspath(__file__))
Phi = lambda z: 0.5 * (1 + erf(z / sqrt(2)))          # noqa: E731
W_CONJ = 0.7


def probs(d, sd, lo_d, hi_d, prior):
    return dict(p_confirm=Phi((-hi_d - d) / sd), p_refute=1 - Phi((lo_d - d) / sd),
                p_excluded={name: 1 - Phi((x + lo_d - d) / sd) for name, x in prior.items()})


def main():
    p = json.load(open(os.path.join(HERE, 'power.json'), encoding='utf-8'))
    scale = sqrt(p['n_pilot_ood'] / p['n_test_ood'])
    z = p['z']
    out = dict(note='предсказательное распределение по пилоту; нормальное приближение; итоговые вероятности — PREREG §7 (смесь и суждение)',
               w_conj=W_CONJ)
    for k in ('R1', 'R2'):
        s = p[k]
        d, se = s['delta_pilot'], s['se_test']
        sd = sqrt(se ** 2 + (se / scale) ** 2)
        prior = {name: v['effect'] for name, v in s['power_prior_descr'].items()}
        cj = s['conj']
        nrm = probs(d, sd, z * se, z * se, prior)
        cnj = probs(d, sd, cj['lower'], cj['upper'], prior)
        hb = cj['dist']['hi_bc']
        cnj['p_only_bc_confirm'] = max(0.0, Phi((-hb - d) / sd) - Phi((-cj['upper'] - d) / sd)) if hb < cj['upper'] else 0.0
        nrm['p_only_bc_confirm'] = 0.0
        mix = dict(p_confirm=W_CONJ * cnj['p_confirm'] + (1 - W_CONJ) * nrm['p_confirm'],
                   p_refute=W_CONJ * cnj['p_refute'] + (1 - W_CONJ) * nrm['p_refute'],
                   p_excluded={m: W_CONJ * cnj['p_excluded'][m] + (1 - W_CONJ) * nrm['p_excluded'][m] for m in prior},
                   p_only_bc_confirm=W_CONJ * cnj['p_only_bc_confirm'])
        out[k] = dict(delta_pilot=d, se_test=se, se_pilot=se / scale, sd_pred=sd, threshold_normal=z * se, lower_conj=cj['lower'],
                      upper_conj=cj['upper'], normal=nrm, conj=cnj, mix=mix)
    json.dump(out, open(os.path.join(HERE, 'expectations.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == '__main__':
    main()
