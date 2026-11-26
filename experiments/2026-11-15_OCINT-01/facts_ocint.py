#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCINT-01: производные числа отчёта, которых нет в json счёта (чтобы ledger.py audit их находил). python3 facts_ocint.py
Вес Б2 — по формуле PREREG §6 из зарегистрированных чисел; прогнозы времени — копия PREREG §4. Это сборка чисел, вердиктов не меняет."""
import json
import os
from math import log2

X = os.path.dirname(os.path.abspath(__file__))
POWER_B2, E4, LEVEL = 0.999, 0.88, 0.0025          # PREREG §6 (мощность при пилотных значениях) и §7 (ожидание E4)
out = dict(source='PREREG-OCINT-01 §4, §6, §7 (коммит c5bb6b32)',
           weight_bits=dict(B2=log2(min(POWER_B2, E4) / LEVEL), B1=0.0, A=0.0),
           forecast_seconds=dict(worlds=7740, quarters_worlds=1150, real=3700))
os.makedirs(os.path.join(X, 'run'), exist_ok=True)
json.dump(out, open(os.path.join(X, 'run', 'facts_ocint.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
