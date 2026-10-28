#!/usr/bin/env python3
"""TRUST-04: ложный уровень, мощность и вес в битах сводных исходов по pilot/pilot_calib.json (PREREG §6);
ложный уровень сводного — наибольший у частей с полом 0,001, мощность — произведение. Сумма ложных уровней семьи
(Бонферрони) — по блокам. → pilot/pilot_bits.json. Запуск из папки опыта: python3 pilot/pilot_bits.py"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
c = json.load(open(os.path.join(HERE, 'pilot_calib.json')))
S = dict(SA=['A1', 'A2', 'A4', 'A5', 'A6', 'A7', 'A8'], SA2=['A11', 'A12'], SB=[f'B{i}' for i in range(1, 8)],
         SB2=[f'B{i}' for i in range(8, 12)], SC=['C_MYOPIC', 'C_DEMES', 'C_POOLED', 'C_COUNCIL', 'C_ORDER'])
out = {}
for k, parts in S.items():
    fl = max(max(c[p]['false_level'], 0.001) for p in parts); pw = math.prod(c[p]['power'] for p in parts)
    out[k] = dict(parts=parts, false_level=fl, power=pw, bits=math.log2(pw / fl))
blocks = dict(A=[f'A{i}' for i in range(1, 15)], B=[f'B{i}' for i in range(1, 16)],
              C=['C_MYOPIC', 'C_DEMES', 'C_POOLED', 'C_COUNCIL', 'C_ORDER'])
out['family_bonferroni'] = {b: sum(max(c[p]['false_level'], 0.001 if c[p]['kind'] == 'интервал' else 0) for p in ps)
                            for b, ps in blocks.items()}
out['family_bonferroni']['всего'] = sum(out['family_bonferroni'].values())
json.dump(out, open(os.path.join(HERE, 'pilot_bits.json'), 'w'), ensure_ascii=False, indent=1)
for k, v in out.items():
    print(k, {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()} if isinstance(v, dict) else v)
