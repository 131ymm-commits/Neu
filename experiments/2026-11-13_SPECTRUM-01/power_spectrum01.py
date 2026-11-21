#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-01: мощность главного правила P3 до прогона → power.json (редакция после совета 48).
P3 подтверждено ⇔ t_align определено не меньше чем в 9 блоках, q0_d64 позже q = 1 не меньше чем в 9 из 10,
и |медиана(отношение/теория) − 1| ≤ 0,10. Модель блока: знак верен с вероятностью p, отношение/теория ~ N(μ, σ).
Сценарии: «по пилоту» — p = 0,99, μ = 0,942 (пилот: 0,927 и 0,957), σ = 0,05; «осторожный» — p = 0,9, μ = 0,942, σ = 0,08.
Оценка Монте-Карло, 20 000 повторов, зерно 303. Ложный уровень P3 — не выше P(X ≥ 9 | n = 10, p = 0,5) = 0,0107
(номинальный нуль для знака; условие на медиану его только уменьшает). Веса (заранее): подтверждение —
log₂(мощность «осторожного» / 0,0107); опровержение — log₂((1 − мощность «по пилоту»)/(1 − 0,0107)); «не решено» — 0.
Проверки метода P1a, P1b, P2 веса не несут (совет 48, п. «ж»)."""
import json, os
from math import comb, log2
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sf = lambda k, n, p: sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))
alpha = sf(9, 10, 0.5)
g = np.random.default_rng(303)


def power(p, mu, sd, reps=20000):
    ok = 0
    for _ in range(reps):
        sign = (g.random(10) < p).sum()
        rel = g.normal(mu, sd, 10)
        ok += sign >= 9 and abs(np.median(rel) - 1) <= 0.10
    return ok / reps


pw = {'по пилоту': power(0.99, 0.942, 0.05), 'осторожный': power(0.9, 0.942, 0.08)}
out = {'false_level_P3': alpha, 'power_P3': pw,
       'weights_bits': {'confirm_P3': log2(pw['осторожный'] / alpha),
                        'refute_P3': min(0.0, log2((1 - pw['по пилоту']) / (1 - alpha))), 'undecided': 0.0,
                        'method_checks': 0.0},
       'series_false_level_weighted': alpha}
json.dump(out, open(os.path.join(HERE, 'power.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
