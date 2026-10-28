#!/usr/bin/env python3
"""TRUST-04: исходы теста в tools/self_calibration.py (строки «(после пилота) ждёт теста» → 1/0 по analysis_trust_04.json).
Исход 1 — «подтверждено», 0 — иначе (как во всей калибровке). Записан после регистрации, до просмотра результатов теста.
Запуск из папки опыта: python3 update_calibration_trust04.py"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
an = json.load(open(os.path.join(HERE, 'analysis_trust_04.json')))
res = dict(an['verdicts'], **an['explore'])
path = os.path.join(ROOT, 'tools', 'self_calibration.py')
src = open(path, encoding='utf-8').read()
pat = re.compile(r"\('TRUST-04', '(?P<id>[A-Z][A-Za-z0-9_]*) (?P<rest>[^']*)', 'PREREG-TRUST-04 §5', 'вероятность', (?P<p>[0-9.]+), None, '\(после пилота\) ждёт теста'\)")
n = 0


def repl(m):
    global n
    k = m['id']
    v = res[k]
    out = 1 if v['outcome'] == 'подтверждено' else 0
    n += 1
    return (f"('TRUST-04', '{k} {m['rest']}', 'PREREG-TRUST-04 §5', 'вероятность', {m['p']}, {out}, "
            f"'(после пилота) тест 600–619: {v['outcome']}')")


new = pat.sub(repl, src)
open(path, 'w', encoding='utf-8').write(new)
print('обновлено строк:', n)
