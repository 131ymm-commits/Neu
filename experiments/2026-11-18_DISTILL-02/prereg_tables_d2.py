#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-02: таблицы пилота для PREREG — печатаются из gha_out/distill02_pilot/pilot.json и gha_out/distill02_pilot2/pilot2.json
(числа не переписываются руками; ERRORS № 200).  python3 prereg_tables_d2.py"""
import json
import os

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
P1 = json.load(open(os.path.join(ROOT, 'gha_out/distill02_pilot/pilot.json'), encoding='utf-8'))
P2 = json.load(open(os.path.join(ROOT, 'gha_out/distill02_pilot2/pilot2.json'), encoding='utf-8'))


def f(x, d=4):
    return '—' if x is None or x != x else f'{x:+.{d}f}'.replace('-', '−').replace('.', ',')


def g(x, d=3):
    return '—' if x is None or x != x else f'{x:.{d}f}'.replace('.', ',')


L = ['**Пилот 1 — сводка** (программы — по пилоту OCDIV-04; среднее по парам «голова × среда»; описательно):', '',
     '| Набор проверки | пар | программа − B1 | больше 0 | программа − Φ-база | больше 0 | доля объяснимого, медиана | три неверных: программа / B1 | K: наблюдённое / из программ, медиана |',
     '|---|---|---|---|---|---|---|---|---|']
for name, ev in P1['eval'].items():
    s = ev['summary']
    L.append(f"| {name} | {s['n_cells']} | {f(s['prog_minus_b1_mean'])} | {s['prog_minus_b1_pos']} | {f(s['prog_minus_phi_mean'])} | {s['prog_minus_phi_pos']} | "
             f"{g(s['explained_median'])} | {g(s['hit_prog_mean'])} / {g(s['hit_b1_mean'])} | {g(s['K_ratio_median'])} |")
L += ['', '**Пилот 2 — меры по средам** (точки; в скобках — ст. откл. повторов, B = ' + str(P2['B']) + '; R = ' + str(P2['R']) + '):', '',
      '| Набор | среда | голов | m1 | m1_phi | m2 | m3 | K наблюдённое / из программ |', '|---|---|---|---|---|---|---|---|']
for name, st in P2['sets'].items():
    for en, e in st['envs'].items():
        pt, sd = e['point'], e['sd']
        L.append(f"| {name} | {en} | {len(e['heads'])} | {f(pt['m1'])} ({g(sd['m1'], 4)}) | {f(pt['m1_phi'])} ({g(sd['m1_phi'], 4)}) | "
                 f"{g(pt['m2'])} ({g(sd['m2'])}) | {f(pt['m3'])} ({g(sd['m3'], 4)}) | {g(pt['K_obs'])} / {g(pt['K_prog'])} |")
L += ['', '**Формулы потери переноса по пилоту OCDIV-04** (P(потеря переноса в разряд j) = σ(…); коэффициенты — две значащие цифры; ε — доля «прочих» ошибок):', '',
      '| Семейство | Голова | формула | ε | Φ-база |', '|---|---|---|---|---|']
for fam in ('T', 'L'):
    for h, fm in P1['formulas'][fam].items():
        terms = ' '.join(f"{w:+.2g}·{n}" for w, n in zip(fm['w_round'][1:], fm['features']))
        ph = P1['formulas_phi'][fam][h]
        L.append(f"| {fam} | {h.split('/')[-1]} | σ({fm['w_round'][0]:+.2g} {terms}) | {g(fm['eps'])} | σ({ph['w_round'][0]:+.2g} {ph['w_round'][1]:+.2g}·phi) |")
print('\n'.join(L).replace('.', ',').replace('σ(', 'σ(') if False else '\n'.join(L))
