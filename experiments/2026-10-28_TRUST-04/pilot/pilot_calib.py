#!/usr/bin/env python3
"""TRUST-04: калибровка предсказаний PREREG §4 по пилоту (зёрна 1100–1109, не тестовые) → pilot/pilot_calib.json.
Знаковые и интервальные: значение на зерне ~ N(среднее, SD) пилота, счёт из 10 — биномиальный; мощность при средних
пилота и при SD × 1,5; ложный уровень знаковых — Bin(10; ½), интервальных — при названной альтернативе.
Эквивалентность (TOST по бутстреп-ДИ 90 %): мощность — доля из 2000 симуляций (выборки по 10 из N(среднее, SD) пилота),
где ДИ внутри (−δ; δ); ложный уровень — то же при истинной разности, равной δ (худший случай).
Ложный уровень сводного — наибольший у частей (ERRORS № 106 (д)); мощность сводного — произведение.
Запуск из папки опыта: python3 pilot/pilot_calib.py"""
import json
import math
import os
import sys

import numpy as np
from scipy.stats import binom, norm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import exp_trust_04 as E  # noqa: E402

FROZEN = {'base': (0.9873, 0.6891), 'r075': (0.5768, 0.3897), 'r095': (1.7134, 1.1968), 'b03': (1.2221, 0.9622),
          'b09': (0.8328, 0.5372)}
DELTA = 0.1
runs = []
for part in ('A', 'B'):
    p = os.path.join(HERE, f'results_trust_04_{part}.json')
    if os.path.exists(p):
        runs += json.load(open(p))['runs']
F = {(r['seed'], r['arm']): r['final'] for r in runs}
seeds = sorted({s for s, _ in F}); arms_present = {a for _, a in F}


def u(a):
    my, far = FROZEN[E.ARMS[a]['world']]
    return np.array([(F[(s, a)]['wG'] - far) / (my - far) for s in seeds])


col = lambda a, k='wG': np.array([F[(s, a)][k] for s in seeds])
P_atleast = lambda p, k, n=10: float(1 - binom.cdf(k - 1, n, p))
p_in = lambda mu, sd, lo, hi: float(norm.cdf((hi - mu) / sd) - norm.cdf((lo - mu) / sd))
out = {}


def interval(name, x, lo, hi, k, alts):
    mu, sd = float(x.mean()), float(x.std(ddof=1))
    fl = {an: P_atleast(p_in(am, sd, lo, hi), k) for an, am in alts.items()}
    out[name] = dict(kind='интервал', mean=mu, sd=sd, k=k, interval=[lo, hi], power=P_atleast(p_in(mu, sd, lo, hi), k),
                     power_sd15=P_atleast(p_in(mu, 1.5 * sd, lo, hi), k), false_level=max(fl.values()), false_by_alt=fl,
                     values=x.round(4).tolist())


def sign(name, a, b, k):
    d = col(a) - col(b); mu, sd = float(d.mean()), float(d.std(ddof=1))
    out[name] = dict(kind='знак', mean=mu, sd=sd, k=k, power=P_atleast(float(norm.cdf(-mu / sd)), k),
                     power_sd15=P_atleast(float(norm.cdf(-mu / (1.5 * sd))), k), false_level=P_atleast(0.5, k),
                     values=d.round(4).tolist())


def tost_rate(mx, sx, my, sy, delta=DELTA, nsim=2000, B=2000, seed=0):
    g = np.random.default_rng(seed); hits = 0
    for _ in range(nsim):
        x = g.normal(mx, sx, 10); y = g.normal(my, sy, 10)
        d = x[g.integers(0, 10, (B, 10))].mean(1) - y[g.integers(0, 10, (B, 10))].mean(1)
        lo, hi = np.quantile(d, 0.05), np.quantile(d, 0.95)
        hits += (-delta < lo) and (hi < delta)
    return hits / nsim


def equiv(name, x, y):
    mx, sx, my, sy = float(x.mean()), float(x.std(ddof=1)), float(y.mean()), float(y.std(ddof=1))
    out[name] = dict(kind='эквивалентность', diff=mx - my, sd_x=sx, sd_y=sy, delta=DELTA,
                     power=tost_rate(mx, sx, my, sy), power_sd15=tost_rate(mx, 1.5 * sx, my, 1.5 * sy, seed=1),
                     false_level=tost_rate(my + DELTA, sx, my, sy, seed=2))


if 'POOLED' in arms_present:
    uD = float(u('DEMES').mean())
    interval('A1', u('POOLED'), -1 / 6, 1 / 6, 8, {'как DEMES': uD, 'у близорукой': 1.0})
    interval('A2', u('POOLED_FREE'), -1 / 6, 1 / 6, 8, {'как DEMES': uD, 'у близорукой': 1.0})
    interval('A3', u('DEMES'), 1 / 6, 5 / 6, 8, {'у дальновидной': 0.0, 'у близорукой': 1.0})
    interval('A4', u('DEMES_FREE'), 1 / 6, 5 / 6, 8, {'у дальновидной': 0.0, 'у близорукой': 1.0})
    sign('A5', 'POOLED', 'DEMES', 9); sign('A6', 'POOLED_FREE', 'DEMES_FREE', 9)
    equiv('A7', u('POOLED'), u('POOLED_FREE')); equiv('A8', u('DEMES'), u('DEMES_FREE'))
    interval('A9', u('DEMES_NOSEL'), 2 / 3, 4 / 3, 9, {'как DEMES': uD})
    interval('A10', u('DEMES_NOSEL_FREE'), 2 / 3, 4 / 3, 9, {'как DEMES': uD})
    interval('A11', u('COUNCIL_SIGN'), -1 / 3, 1 / 3, 8, {'у близорукой': 1.0, 'как DEMES': uD})
    equiv('A12', u('COUNCIL'), u('COUNCIL_SIGN'))
    interval('A13', u('COUNCIL'), -1 / 6, 1 / 6, 9, {'как DEMES': uD, 'у близорукой': 1.0})
    interval('A14', u('MYOPIC'), 2 / 3, 4 / 3, 9, {'у дальновидной': 0.0})
if 'POOLED_r075' in arms_present:
    for i, c in enumerate(('r075', 'r095', 'b03', 'b09', 'IND', 'MIG')):
        sign(f'B{i + 1}', f'POOLED_{c}', f'DEMES_{c}', 9)
    for i, w in enumerate(('r075', 'r095', 'b03', 'b09')):
        uDw = float(u(f'DEMES_{w}').mean())
        interval(f'B{i + 7}', u(f'POOLED_{w}'), -1 / 3, 1 / 3, 8, {'как DEMES этого мира': uDw, 'у близорукой': 1.0})
        interval(f'B{i + 11}', u(f'MYOPIC_{w}'), 2 / 3, 4 / 3, 9, {'у дальновидной': 0.0})
    sign('EB1', 'POOLED', 'POOLED_IND', 7); sign('EB2', 'POOLED', 'POOLED_MIG', 7); sign('EB3', 'DEMES', 'DEMES_MIG', 7)
out['arms'] = {a: dict(u_mean=float(u(a).mean()), u_sd=float(u(a).std(ddof=1)), u=u(a).round(4).tolist(),
                       sd_groups=float(col(a, 'wG_sd_groups').mean()), price_within=float(col(a, 'price_within').mean()),
                       logloss=float(col(a, 'logloss').mean())) for a in E.ARMS if a in arms_present}
json.dump(out, open(os.path.join(HERE, 'pilot_calib.json'), 'w'), ensure_ascii=False, indent=1)
for k, v in out.items():
    if k == 'arms':
        continue
    m = v.get('mean', v.get('diff'))
    print(f"{k:5s} {v['kind']:16s} {m:+.4f}  мощность {v['power']:.3f} ({v['power_sd15']:.3f})  ложный {v['false_level']:.4g}")
for a, v in out['arms'].items():
    print(f"  {a:18s} u {v['u_mean']:+.4f} ± {v['u_sd']:.4f}  SD групп {v['sd_groups']:.3f}  ll {v['logloss']:.4f}")
