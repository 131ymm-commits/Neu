#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-01: мощность правил «не меньше 9 из 10 блоков» до прогона → power.json.
Ложный уровень правила — P(X ≥ 9 | n = 10, p = 0,5) (номинальный нуль «в блоке как монета»; для P1 и P3 настоящий
нуль даёт меньшую долю, так что это верхняя граница). Мощность — P(X ≥ 9) при доле успеха блока p:
«по пилоту» p = 0,99 (2 из 2 блоков с запасом), «вдвое слабее» p = 0,9. Для P3 дополнительно — вероятность, что
медиана отношения попадёт в [1,05; 1,40] при отношении блока ~ N(1,19; 0,05) (пилот: 1,214 и 1,167), оценка
Монте-Карло, 20 000 повторов, зерно 303. Правило весов (заранее): подтверждение — «вдвое слабее»;
неподтверждение — log₂((1 − мощность «по пилоту»)/(1 − ложный уровень)), не больше 0."""
import json, os
from math import comb, log2
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sf = lambda k, n, p: sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))
alpha = sf(9, 10, 0.5)
g = np.random.default_rng(303)
med_in = float(np.mean([1.05 <= np.median(g.normal(1.19, 0.05, 10)) <= 1.40 for _ in range(20000)]))
pw = {'по пилоту': sf(9, 10, 0.99), 'вдвое слабее': sf(9, 10, 0.9)}
out = {'false_level_9of10': alpha, 'power': pw, 'P3_median_in_interval_mc': med_in,
       'weights_bits': {'confirm': log2(pw['вдвое слабее'] / alpha),
                        'confirm_P3': log2(pw['вдвое слабее'] * med_in / alpha),
                        'disconfirm': min(0.0, log2((1 - pw['по пилоту']) / (1 - alpha)))},
       'series_false_level_bonferroni_5_rules': 5 * alpha}
json.dump(out, open(os.path.join(HERE, 'power.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
