#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-02: ожидания до прогона (PREREG §6) — из prereg_power_d2.json; вероятность = 0,95 × решающая мощность по пилоту 2 при τ пилота
(как в OCDIV-03/04); при τ из верхней границы — рядом, описательно. Пишет expect_d2.json и печатает строки для tools/self_calibration.py.
  python3 prereg_expect_d2.py"""
import json
import os

X = os.path.dirname(os.path.abspath(__file__))
PW = json.load(open(os.path.join(X, 'prereg_power_d2.json'), encoding='utf-8'))['rules']
TEXT = {'Р1-Т': 'Р1-Т подтверждено: программа лучше частот смещений (B1) по лог-вероятности ответа, «тысячи», 8 сред',
        'Р1-Л': 'Р1-Л подтверждено: то же на «длине», 3 среды (часть А)',
        'Р1Ф-Т': 'Р1Ф-Т подтверждено: программа лучше Φ-базы (Wen и др.), «тысячи»',
        'Р1Ф-Л': 'Р1Ф-Л подтверждено: программа лучше Φ-базы, «длина» (часть А)',
        'Р2-Т': 'Р2-Т подтверждено: программа берёт больше половины объяснимого (против ящика), «тысячи»',
        'Р2-Л': 'Р2-Л подтверждено: то же на «длине» — описательно (мощность ниже 0,2)',
        'Р3-Т': 'Р3-Т решающий вердикт в любую сторону: совпадение ошибок голов ≠ программам, «тысячи»',
        'Р3-Л': 'Р3-Л решающий вердикт в любую сторону: то же на «длине» (часть А)',
        'Р4-Т': 'Р4-Т подтверждено: перенос — программа лучше B1 на новых средах (пятизначные a), часть А'}
KEY = {r: (f'{r}:решающий' if r.startswith('Р3') else f'{r}:подтверждено') for r in TEXT}


def c(x, d):
    return f'{x:.{d}f}'.replace('.', ',')


E = []
for i, r in enumerate(TEXT, 1):
    e = PW[r]
    E.append(dict(id=f'E{i}', rule=r, key=KEY[r], p=round(0.95 * e['decisive'], 6), trivial=False, text=TEXT[r],
                  basis=f"0,95 × решающая мощность {c(e['decisive'], 6)} при τ = {c(e['tau'], 4)} (при τ из верхней границы {c(e['tau_hi'], 4)} — "
                        f"{c(e['decisive_tau_hi'], 6)})"))
E.append(dict(id=f'E{len(E) + 1}', rule=None, key='method', p=0.95, trivial=True, text='опыт определён: в каждом семействе годны все среды теста',
              basis='тривиальное: в пилоте у всех сред 7 голов'))
json.dump(dict(source='prereg_power_d2.json (пилот 2, gha_out/distill02_pilot2/pilot2.json)', rule='вероятность = 0,95 × решающая мощность при τ пилота',
               expectations=E), open(os.path.join(X, 'expect_d2.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for e in E:
    note = ('(после пилота) тривиальное — вне сводной калибровки; ' if e['trivial'] else '') + e['basis'] + '; expect_d2.json; ждёт результата'
    print(repr(('DISTILL-02', f"{e['id']} {e['text']}", 'PREREG-DISTILL-02 §6', 'вероятность', round(e['p'], 4), None, note)) + ',')
