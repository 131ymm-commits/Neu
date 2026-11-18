#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-02: мощность правил PREREG по пилоту 2 (gha_out/distill02_pilot2/pilot2.json) — с тем числом сред и частями, какие будут
в тесте; модель «новая среда» (`ocdiv4.power_entry4`), 200 000 наборов. Пишет prereg_power_d2.json и печатает таблицу для PREREG.
  python3 prereg_power_d2.py"""
import json
import os
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
sys.path.insert(0, X)
import distill02 as D  # noqa: E402

P = json.load(open(os.path.join(ROOT, 'gha_out/distill02_pilot2/pilot2.json'), encoding='utf-8'))
# правило → (набор пилота 2, число сред в тесте); мера, вид, часть Б и сдвиг — из distill02.RULES
SOURCE = {'Р1-Т': ('T_test3', 8), 'Р1-Л': ('L_test3', 3), 'Р1Ф-Т': ('T_test3', 8), 'Р1Ф-Л': ('L_test3', 3), 'Р2-Т': ('T_test3', 8),
          'Р2-Л': ('L_test3', 3), 'Р3-Т': ('T_test3', 8), 'Р3-Л': ('L_test3', 3), 'Р4-Т': ('T_transfer', 3)}


def g(x, d=3):
    return '—' if x is None else f'{x:.{d}f}'.replace('.', ',')


def f(x, d=4):
    return '—' if x is None else f'{x:+.{d}f}'.replace('-', '−').replace('.', ',')


out, rows = {}, []
for rule, (fam, ph, meas, kind, part_b, shift) in D.RULES.items():
    src, m = SOURCE[rule]
    envs = P['sets'][src]['envs']
    pts = [envs[n]['point'][meas] for n in sorted(envs)]
    sds = [envs[n]['sd'][meas] for n in sorted(envs)]
    e = D.power_rule(pts, sds, 1.0, m, part_b, shift)
    dec = (e['power']['confirm'] + e['power']['refute']) if kind == 'two' else e['power']['confirm']
    dec_hi = (e['power_tau_hi']['confirm'] + e['power_tau_hi']['refute']) if kind == 'two' else e['power_tau_hi']['confirm']
    e.update(decisive=dec, decisive_tau_hi=dec_hi, source=src, m=m, active=bool(dec >= D.POWER_MIN))
    out[rule] = e
    rows.append(f"| {rule} | {src} | {m} | {meas}{' − ' + g(shift, 1) if shift else ''} | {'двусторонний' if kind == 'two' else 'больше'} | "
                f"{'А и Б' if part_b else 'А'} | {f(e['mu'])} | {g(e['tau'], 4)} | {g(e['s_test'], 4)} | {g(e['power']['part_a'])} | "
                f"{g(e['power']['part_b'])} | {g(dec)} | {g(dec_hi)} (τ = {g(e['tau_hi'], 4)}) | {'правило' if e['active'] else 'описательно'} |")
json.dump(dict(source='gha_out/distill02_pilot2/pilot2.json', power_min=D.POWER_MIN, rules=out), open(os.path.join(X, 'prereg_power_d2.json'), 'w',
          encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
print('| Правило | набор пилота 2 | сред в тесте | мера | вид | части | μ | τ | s | часть А | часть Б | решающая | при τ из верхней границы | итог |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
print('\n'.join(rows))
print('\nRULES_ACTIVE =', {r: e['active'] for r, e in out.items()})
