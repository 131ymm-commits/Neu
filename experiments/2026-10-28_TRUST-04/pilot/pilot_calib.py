#!/usr/bin/env python3
"""TRUST-04: калибровка предсказаний PREREG §4 по пилоту (зёрна 1100–1109, не тестовые) → pilot/pilot_calib.json.
Знаковые и интервальные: значение на зерне ~ N(среднее, SD) пилота, счёт из 10 — биномиальный; мощность при средних
пилота и при SD × 1,5; ложный уровень знаковых — Bin(10; ½), интервальных — при названной альтернативе.
Эквивалентность (TOST по ДИ Уэлча 90 %): мощность — доля из 20 000 симуляций (выборки по 10 из N(среднее, SD) пилота),
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
import glob
for p in sorted(glob.glob(os.path.join(HERE, 'results_trust_04_*.json'))):
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


def tost_rate(mx, sx, my, sy, delta=DELTA, nsim=20000, seed=0):
    """Доля симуляций (по 10 значений из N пилота), где ДИ Уэлча 90 % разности средних внутри (−δ; δ)."""
    from scipy.stats import t as tdist
    g = np.random.default_rng(seed)
    x = g.normal(mx, sx, (nsim, 10)); y = g.normal(my, sy, (nsim, 10))
    vx, vy = x.var(1, ddof=1) / 10, y.var(1, ddof=1) / 10; se = np.sqrt(vx + vy)
    df = (vx + vy) ** 2 / (vx ** 2 / 9 + vy ** 2 / 9); h = tdist.ppf(0.95, df) * se; d = x.mean(1) - y.mean(1)
    return float(np.mean((d - h > -delta) & (d + h < delta)))


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
    conds = [c for c in ('r075', 'r095', 'b03', 'b09', 'IND', 'MIG', 'SIG5') if f'POOLED_{c}' in arms_present]
    for c in conds:
        sign(f'B{1 + ["r075", "r095", "b03", "b09", "IND", "MIG", "SIG5"].index(c)}', f'POOLED_{c}', f'DEMES_{c}', 9)
    for i, w in enumerate(('r075', 'r095', 'b03', 'b09')):
        uDw = float(u(f'DEMES_{w}').mean())
        interval(f'B{i + 8}', u(f'POOLED_{w}'), -1 / 3, 1 / 3, 8, {'как DEMES этого мира': uDw, 'у близорукой': 1.0})
        interval(f'B{i + 12}', u(f'MYOPIC_{w}'), 2 / 3, 4 / 3, 9, {'у дальновидной': 0.0})
    _d1 = np.abs(u('POOLED')) - np.abs(u('POOLED_IND')); _mu, _sd = float(_d1.mean()), float(_d1.std(ddof=1))
    out['EB1'] = dict(kind='знак', mean=_mu, sd=_sd, k=7, power=P_atleast(float(norm.cdf(-_mu / _sd)), 7),
                      power_sd15=P_atleast(float(norm.cdf(-_mu / (1.5 * _sd))), 7), false_level=P_atleast(0.5, 7), values=_d1.round(4).tolist())
    equiv('EB2', u('POOLED_MIG'), u('POOLED')); sign('EB3', 'DEMES', 'DEMES_MIG', 7)
    for _w in ('r075', 'r095', 'b03', 'b09'):
        equiv(f'EB5_{_w}', u(f'DEMES_{_w}'), u('DEMES'))
    if 'DEMES_SIG5' in arms_present:
        sign('EB4', 'DEMES', 'DEMES_SIG5', 7)
# блок В: независимая реализация (пилот 1200–1204) против основного пилота; мощность — при n = 10 у обеих
IP = os.path.join(os.path.dirname(HERE), 'indep', 'pilot', 'results_indep_04.json')
if os.path.exists(IP) and 'POOLED' in arms_present:
    ir = json.load(open(IP))['runs']
    for a in ('MYOPIC', 'DEMES', 'POOLED', 'COUNCIL'):
        ui = np.array([r['u'] for r in ir if r['arm'] == a])
        x, y = ui, u(a)
        out[f'C_{a}'] = dict(kind='эквивалентность', diff=float(x.mean() - y.mean()), sd_x=float(x.std(ddof=1)), sd_y=float(y.std(ddof=1)),
                             n_indep_pilot=len(ui), delta=DELTA, power=tost_rate(x.mean(), x.std(ddof=1), y.mean(), y.std(ddof=1)),
                             power_sd15=tost_rate(x.mean(), 1.5 * x.std(ddof=1), y.mean(), 1.5 * y.std(ddof=1), seed=1),
                             false_level=tost_rate(y.mean() + DELTA, x.std(ddof=1), y.mean(), y.std(ddof=1), seed=2))
    dp = np.array([r['u'] for r in ir if r['arm'] == 'POOLED']) - np.array([r['u'] for r in ir if r['arm'] == 'DEMES'])
    out['C_ORDER'] = dict(kind='знак', mean=float(dp.mean()), sd=float(dp.std(ddof=1)), k=9,
                          power=P_atleast(float(norm.cdf(-dp.mean() / dp.std(ddof=1))), 9),
                          power_sd15=P_atleast(float(norm.cdf(-dp.mean() / (1.5 * dp.std(ddof=1)))), 9), false_level=P_atleast(0.5, 9))
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
