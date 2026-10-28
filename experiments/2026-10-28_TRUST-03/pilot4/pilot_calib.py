#!/usr/bin/env python3
"""TRUST-03, пилот 4: калибровка предсказаний PREREG §4 по зёрнам 970–977 (не тестовые) →
pilot4/pilot_calib.json, печать таблицы. Нормальное приближение для значения на зерне (среднее и SD по зёрнам пилота),
затем биномиальный счёт из 10. Мощность — при средних пилота (и при SD × 1,5); ложный уровень интервальных — при
названной альтернативе (то же SD, среднее сдвинуто к альтернативе); знаковых — Bin(10, ½). Пол ложного уровня в битах —
0,001 (CLAUDE.md). Для сводного исхода ложный уровень — наибольший у частей (ERRORS № 106 (д)), мощность — произведение.
Запуск из папки опыта: python3 pilot4/pilot_calib.py"""
import json
import math
import os

import numpy as np
from scipy.stats import binom, norm

HERE = os.path.dirname(os.path.abspath(__file__))
W_MY, W_FAR = 0.9873, 0.6891
D = W_MY - W_FAR
r = json.load(open(os.path.join(HERE, 'results_trust_03.json')))
F = {(x['seed'], x['arm']): x['final'] for x in r['runs']}
seeds = sorted({s for s, _ in F})
col = lambda a, k='wG': np.array([F[(s, a)][k] for s in seeds])
u = lambda a: (col(a) - W_FAR) / D
P_atleast = lambda p, k: float(1 - binom.cdf(k - 1, 10, p))


def p_in(mu, sd, lo, hi):
    return float(norm.cdf((hi - mu) / sd) - norm.cdf((lo - mu) / sd))


out = {}


def interval(name, x, lo, hi, k, alts):
    mu, sd = float(x.mean()), float(x.std(ddof=1))
    pw = P_atleast(p_in(mu, sd, lo, hi), k); pw15 = P_atleast(p_in(mu, 1.5 * sd, lo, hi), k)
    fl = {a_name: P_atleast(p_in(a_mu, sd, lo, hi), k) for a_name, a_mu in alts.items()}
    out[name] = dict(kind='интервал', values=x.round(4).tolist(), mean=mu, sd=sd, k=k, interval=[lo, hi], power=pw,
                     power_sd_x1_5=pw15, false_level_by_alt=fl, false_level=max(fl.values()))


def sign(name, x, k):                                       # «разность < 0» на зерне
    mu, sd = float(x.mean()), float(x.std(ddof=1))
    p = float(norm.cdf(-mu / sd)); p15 = float(norm.cdf(-mu / (1.5 * sd)))
    out[name] = dict(kind='знак', values=x.round(5).tolist(), mean=mu, sd=sd, k=k, power=P_atleast(p, k),
                     power_sd_x1_5=P_atleast(p15, k), false_level=P_atleast(0.5, k))


uD = float(u('DEMES').mean())
interval('P1', u('MYOPIC'), 2 / 3, 4 / 3, 9, {'MYOPIC у дальновидной (u = 0)': 0.0})
interval('P2', u('COUNCIL'), -1 / 6, 1 / 6, 9, {'COUNCIL у близорукой (u = 1)': 1.0})
out['P2']['pass_if_partial_like_DEMES'] = P_atleast(p_in(uD, out['P2']['sd'], -1 / 6, 1 / 6), 9)  # различение, не ложный уровень
sign('P3', col('COUNCIL', 'logloss') - col('MYOPIC', 'logloss'), 9)
interval('P5', u('DEMES'), 1 / 6, 5 / 6, 8, {'DEMES у близорукой (u = 1)': 1.0, 'DEMES у дальновидной (u = 0)': 0.0})
sign('P6', col('DEMES') - col('DEMES_10x40'), 8)
interval('P7', u('DEMES_NOSEL'), 2 / 3, 4 / 3, 9, {'DEMES_NOSEL как DEMES': uD})
sign('P9', col('COUNCIL') - col('DEMES'), 9)
sign('P10', col('DEMES') - col('DEMES_NOSEL'), 9)
sign('P11', col('DEMES_NOWITHIN') - col('DEMES'), 9)
interval('P12', u('DEMES_NOWITHIN'), -1 / 6, 1 / 6, 8, {'DEMES_NOWITHIN как DEMES': uD})
sign('E1', col('COUNCIL', 'self_dec') - col('MYOPIC', 'self_dec'), 7)
interval('E2', u('COUNCIL_10x40'), -1 / 3, 1 / 3, 8, {'COUNCIL_10x40 у близорукой (u = 1)': 1.0})
sign('E3', col('COUNCIL') - col('COUNCIL_IND'), 7)
sign('E4', col('DEMES') - col('DEMES_IND'), 7)
fam = ['P1', 'P2', 'P3', 'P5', 'P6', 'P7', 'P9', 'P10', 'P11', 'P12']
out['family_false_level_bonferroni'] = float(sum(max(out[p]['false_level'], 0.0) for p in fam))
out['family_false_level_bonferroni_floor'] = float(sum(max(out[p]['false_level'], 0.001) for p in fam))
for sname, parts in (('S1', ['P2', 'P3', 'P9']), ('S2', ['P5', 'P10']), ('S3', ['P11', 'P12'])):
    fl = max(max(out[p]['false_level'], 0.001) for p in parts)
    pw = float(np.prod([out[p]['power'] for p in parts]))
    out[sname] = dict(parts=parts, false_level=fl, power=pw, bits=math.log2(pw / fl))
# описательно: части Прайса и SD между группами
out['price'] = {a: dict(within=col(a, 'price_within').round(5).tolist(), between=col(a, 'price_between').round(5).tolist())
                for a in sorted({a for _, a in F})}
out['wG_by_arm'] = {a: dict(mean=float(col(a).mean()), sd=float(col(a).std(ddof=1)), values=col(a).round(4).tolist(),
                            sd_groups=float(col(a, 'wG_sd_groups').mean())) for a in sorted({a for _, a in F})}
out['seeds'] = seeds
json.dump(out, open(os.path.join(HERE, 'pilot_calib.json'), 'w'), ensure_ascii=False, indent=1)
for k in fam + ['E1', 'E2', 'E3', 'E4']:
    v = out[k]
    print(f"{k:4s} {v['kind']:8s} среднее {v['mean']:+.4f} SD {v['sd']:.4f}  мощность {v['power']:.3f} ({v['power_sd_x1_5']:.3f})"
          f"  ложный {v['false_level']:.4g}  {v['values']}")
print('P2 при «частичном пути, как DEMES»:', round(out['P2']['pass_if_partial_like_DEMES'], 3))
print('семья по Бонферрони:', round(out['family_false_level_bonferroni'], 4), '(с полом 0,001:',
      round(out['family_false_level_bonferroni_floor'], 4), ')')
for s in ('S1', 'S2', 'S3'):
    print(s, out[s]['parts'], 'ложный', round(out[s]['false_level'], 4), 'мощность', round(out[s]['power'], 3), 'бит', round(out[s]['bits'], 2))
for a, v in out['wG_by_arm'].items():
    print(f"  {a:15s} w_G {v['mean']:.4f} ± {v['sd']:.4f}  SD групп {v['sd_groups']:.3f}  {v['values']}")
