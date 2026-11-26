#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-04: ожидания до прогона (PREREG §6) — из разбора пилота и третьего контроля; числа не переписываются руками (ERRORS № 200).
  python3 prereg_expect4.py    пишет expect_ocdiv4.json рядом со скриптом и печатает строки для tools/self_calibration.py
Правило: вероятность = 0,95 × решающая мощность по пилоту (как в OCDIV-03). Для Р1-Т — при τ из верхней границы (совет 72, «нужно» 5;
HYPOTHESIS-ADDENDUM-2), для остальных — при τ пилота. Первичный нуль Р1 — по константе N3C_FIT (исход третьего контроля)."""
import json
import os
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
sys.path.insert(0, X)
import ocdiv4 as C  # noqa: E402

P = json.load(open(os.path.join(ROOT, 'gha_out/ocdiv4_sum_pilot3/pilot.json'), encoding='utf-8'))
K = json.load(open(os.path.join(ROOT, 'gha_out/ocdiv4_control3/control3.json'), encoding='utf-8'))
assert K['n3c_fit'] is C.N3C_FIT, 'N3C_FIT не совпадает с выводом третьего контроля'
nul, alt = ('N3c', 'N0c') if C.N3C_FIT else ('N0c', 'N3c')
alt_power = (lambda r: P['power_alt'][r + ' (N0c)']) if C.N3C_FIT else (lambda r: P['power'][r])


def p95(x):
    return round(0.95 * x, 6)


def c(x, d):
    return f'{x:.{d}f}'.replace('.', ',')


T = lambda r: r == 'Р1-Т'   # noqa: E731  у Р1-Т — τ из верхней границы
pt, pl = C.primary_power(P, 'Р1-Т', C.N3C_FIT), C.primary_power(P, 'Р1-Л', C.N3C_FIT)
at, al = alt_power('Р1-Т'), alt_power('Р1-Л')
p2 = C.primary_power(P, 'Р2-Т', C.N3C_FIT)
act = C.RULES_ACTIVE
E = [
    dict(id='E1', key='Р1-Л:подтверждено', p=p95(C.decisive(pl, 'pos')), trivial=False,
         text=f"Р1-Л подтверждено (нуль {nul}; часть А, три среды «длины»)" + ('' if act['Р1-Л'] else ' — описательно'),
         basis=f"0,95 × мощность {c(pl['power']['confirm'], 6)} при τ = {c(pl['tau'], 4)}"),
    dict(id='E2', key='Р1-Л:опровергнуто', p=p95(pl['power']['refute']), trivial=False,
         text=f"Р1-Л опровергнуто (нуль {nul})", basis=f"0,95 × мощность «опровергнуто» {c(pl['power']['refute'], 6)} при τ = {c(pl['tau'], 4)}"),
    dict(id='E3', key='Р1-Т:подтверждено', p=p95(C.decisive(pt, 'pos', tau_hi=True)), trivial=False,
         text=f"Р1-Т подтверждено (нуль {nul}; обе части)" + ('' if act['Р1-Т'] else ' — описательно, заранее неинформативно'),
         basis=f"0,95 × мощность {c(pt['power_tau_hi']['confirm'], 6)} при τ из верхней границы {c(pt['tau_hi'], 4)} "
               f"(при τ пилота {c(pt['tau'], 4)} — {c(pt['power']['confirm'], 6)})"),
    dict(id='E4', key='alt:Р1-Т:подтверждено', p=p95(C.decisive(at, 'pos', tau_hi=True)), trivial=False,
         text=f"ветвь {alt} (описательно): Р1-Т подтверждено тем же правилом",
         basis=f"0,95 × мощность {c(at['power_tau_hi']['confirm'], 6)} при τ из верхней границы {c(at['tau_hi'], 4)} "
               f"(при τ пилота {c(at['tau'], 4)} — {c(at['power']['confirm'], 6)}, ожидание {c(0.95 * at['power']['confirm'], 4)})"),
    dict(id='E5', key='alt:Р1-Л:подтверждено', p=p95(C.decisive(al, 'pos')), trivial=False,
         text=f"ветвь {alt} (описательно): Р1-Л подтверждено тем же правилом",
         basis=f"0,95 × мощность {c(al['power']['confirm'], 6)} при τ = {c(al['tau'], 4)}"),
    dict(id='E6', key='Р2-Т:решающий', p=p95(C.decisive(p2, 'two')), trivial=False,
         text='Р2-Т (описательно): решающий вердикт в любую сторону',
         basis=f"0,95 × (вверх {c(p2['power']['confirm'], 6)} + вниз {c(p2['power']['refute'], 6)}) при τ = {c(p2['tau'], 4)}"),
    dict(id='E7', key='method', p=0.95, trivial=True, text='опыт определён по обоим семействам (годны ≥ 6 сред «тысяч» и ≥ 2 «длины»)',
         basis='тривиальное: невырождены все 11 сред пилота'),
]
out = dict(source='gha_out/ocdiv4_sum_pilot3/pilot.json (третий разбор пилота, 97128d95) и gha_out/ocdiv4_control3/control3.json (n3c_fit)',
           p_method=0.95, rule='вероятность = 0,95 × решающая мощность по пилоту; Р1-Т — при τ из верхней границы (совет 72)',
           primary_null=nul, rules_active=act, expectations=E)
json.dump(out, open(os.path.join(X, 'expect_ocdiv4.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for e in E:
    note = ('(после пилота) тривиальное — вне сводной калибровки; ' if e['trivial'] else '') + e['basis'] + '; expect_ocdiv4.json; ждёт результата'
    print(repr(('OCDIV-04', f"{e['id']} {e['text']}", 'PREREG-OCDIV-04 §6', 'вероятность', round(e['p'], 4), None, note)) + ',')
