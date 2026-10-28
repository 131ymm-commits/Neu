#!/usr/bin/env python3
"""TRUST-02: калибровка кромок по пилоту на 5 зёрнах (993–997; в тест не входят) — ворота 4 (д) и находка 8 проверки
по трём линзам. Для каждого основного предсказания печатает: среднее и SD статистики по зёрнам пилота; вероятность пройти
в одном зерне (нормальное приближение) и мощность P(≥ k из 10); значение статистики у названной альтернативы и
вероятность пройти при ней с тем же шумом — это ложный уровень интервального предсказания. Пишет pilot/pilot_calib.json.
Запуск: python3 pilot_calib.py"""
import json
import math
import os

import numpy as np

import exp_trust_02 as E

d = json.load(open(os.path.join(E.HERE, 'pilot', 'results_trust_02.json')))
seeds = d['params']['SEEDS']
R = {(r['seed'], r['arm']): r for r in d['runs']}
WB, WG, WA = E.WB, E.WG, E.WA
wB = WB.exact_weights(); idB = WB.identifiable(wB); nB = WB.identifiable(WB.naive_weights())
Phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))


def tail(p, k=9, n=10):
    return sum(math.comb(n, j) * p ** j * (1 - p) ** (n - j) for j in range(k, n + 1))


def rho(w):
    i = WB.identifiable(w); s = np.linalg.norm(i[1:3]) / np.linalg.norm(idB[1:3])
    return (i[3] / idB[3]) / s, (i[4] / idB[4]) / s


def stat(arm, f):
    return np.array([f(R[(s, arm)]) for s in seeds])


rows = {}
mad = stat('KELLY_B', lambda r: np.abs(WB.identifiable(r['w_final']) - idB).mean())
scl = stat('KELLY_B', lambda r: WB.scale(r['w_final']) / WB.scale(wB))
sdB = stat('KELLY_B', lambda r: r['exact']['self_dec'])
r1 = stat('KELLY_B', lambda r: rho(r['w_final'])[0]); r2 = stat('KELLY_B', lambda r: rho(r['w_final'])[1])
w0d = stat('KELLY_B', lambda r: abs(WB.identifiable(r['w_final'])[0] - idB[0]))
sdI = stat('INDEP_B', lambda r: r['exact']['self_dec']); scI = stat('INDEP_B', lambda r: WB.scale(r['w_final']) / WB.scale(wB))
sdK = stat('KLUCK_B', lambda r: r['exact']['self_dec'])
dM1 = stat('CONTEST_A', lambda r: r['exact']['self_dec']) - stat('KELLY6_A', lambda r: r['exact']['self_dec'])
c40 = stat('CONTEST_A', lambda r: r['exact']['self_dec']); c400 = stat('CONTEST400_A', lambda r: r['exact']['self_dec'])
wG = stat('KELLY_G', lambda r: r['w_final'][1 + E.G_IDX])
wGb = stat('KELLY_G', lambda r: WG.with_b(r['b_final']).exact_weights()[1 + E.G_IDX])
xll = stat('KELLY_G', lambda r: r['excess_logloss_snap_mean']); xllF = stat('KELLY_GFIX', lambda r: r['excess_logloss_snap_mean'])
m = lambda x: (float(np.mean(x)), float(np.std(x, ddof=1)))

# альтернативы (точные значения статистик)
nv = WB.naive_weights(); nv08 = nv.copy(); nv08[1:] *= 0.8
alt = {}
for tag, w in (('наивная', nv), ('наивная ×0,8', nv08)):
    i = WB.identifiable(w)
    alt[tag] = dict(mad=float(np.abs(i - idB).mean()), scale=WB.scale(w) / WB.scale(wB), sd=WB.exact_metrics(w)['self_dec'],
                    rho=rho(w))
wA = WA.exact_weights(); b_h = E.b_of(wA[1 + E.G_IDX]); wgh = WG.with_b(b_h)
alt['честная формула в своём мире G'] = dict(b=b_h, xll=wgh.exact_metrics(wA)['logloss'] - wgh.exact_metrics(wgh.exact_weights())['logloss'],
                                            wG=float(wA[1 + E.G_IDX]), wG_bayes=float(wgh.exact_weights()[1 + E.G_IDX]))
out = dict(seeds=seeds, alt=alt)


def interval(name, x, lo=None, hi=None, k=9, alt_value=None):
    mu, sd = m(x)
    p = (Phi((hi - mu) / sd) if hi is not None else 1) * (1 - Phi((lo - mu) / sd) if lo is not None else 1)
    pa = None
    if alt_value is not None:
        pa = (Phi((hi - alt_value) / sd) if hi is not None else 1) * (1 - Phi((lo - alt_value) / sd) if lo is not None else 1)
    rec = dict(mean=mu, sd=sd, pilot_pass=int(sum((lo is None or v >= lo) and (hi is None or v <= hi) for v in x)),
               p_seed=p, power=tail(p, k), p_seed_x15=None, alt_value=alt_value, p_alt_seed=pa,
               false_level=None if pa is None else tail(pa, k))
    sd2 = 1.5 * sd   # проверка устойчивости: SD по 5 зёрнам занижена
    p2 = (Phi((hi - mu) / sd2) if hi is not None else 1) * (1 - Phi((lo - mu) / sd2) if lo is not None else 1)
    rec['p_seed_x15'] = p2; rec['power_x15'] = tail(p2, k)
    out[name] = rec
    print(f"{name:28s} среднее {mu:+.4f} SD {sd:.4f}; в пилоте {rec['pilot_pass']}/5; P(зерно) {p:.3f}; мощность {rec['power']:.3f} "
          f"(SD×1,5: {rec['power_x15']:.3f})" + ('' if pa is None else f"; альтернатива {alt_value:+.4f}: P(зерно) {pa:.3g}, "
                                                                        f"ложный уровень {rec['false_level']:.3g}"))


print('альтернативы:', json.dumps(alt, ensure_ascii=False, default=float))
mu, sd = m(mad)
out['R1_mad_mean'] = dict(mean=mu, sd=sd, p=Phi((0.25 - mu) / (sd / math.sqrt(10))),
                          p_alt_naive08=Phi((0.25 - alt['наивная ×0,8']['mad']) / (sd / math.sqrt(10))))
print(f"R1 MAD (среднее по 10)     среднее {mu:.4f} SD {sd:.4f}; P(≤ 0,25) {out['R1_mad_mean']['p']:.4f}; при наивной ×0,8 "
      f"({alt['наивная ×0,8']['mad']:.3f}) {out['R1_mad_mean']['p_alt_naive08']:.3g}")
interval('R1 масштаб', scl, 0.9, 1.2, alt_value=alt['наивная ×0,8']['scale'])
interval('R1 |самообман|', np.abs(sdB), None, 0.015, alt_value=abs(alt['наивная ×0,8']['sd']))
rk1, rk2 = (1 + nB[3] / idB[3]) / 2, (1 + nB[4] / idB[4]) / 2
interval('R3 ρ пары 1', r1, None, rk1, alt_value=alt['наивная']['rho'][0])
interval('R3 ρ пары 2', r2, None, rk2, alt_value=alt['наивная']['rho'][1])
interval('R4 |w0 − точный|', w0d, None, 0.4, alt_value=abs(idB[0] - E.lg(0.3)))
interval('R5 самообман INDEP_B', sdI, 0.015, None)
interval('R5 масштаб INDEP_B', scI, 1.5, None)
interval('R6 |самообман KLUCK_B|', np.abs(sdK), None, 0.015, alt_value=float(np.mean(sdI)))
interval('M1 CONTEST − KELLY6', dM1, 0.0, None)
interval('M1 CONTEST − KELLY6 (≥ 8)', dM1, 0.0, None, k=8)
interval('M2 CONTEST400 − CONTEST', c400 - c40, None, 0.0)
mu4, mu40 = float(np.mean(c400)), float(np.mean(c40))
out['M2_ratio'] = dict(ratio=mu4 / mu40, mean400=mu4, mean40=mu40)
print(f"M2 отношение средних {mu4 / mu40:.3f} (кромка 0,5)")
interval('G1 вес G', wG, None, 0.75 * E.W_REF, alt_value=alt['честная формула в своём мире G']['wG'])
interval('G1 |вес − байес(b)|', np.abs(wG - wGb), None, 0.2,
         alt_value=abs(alt['честная формула в своём мире G']['wG'] - alt['честная формула в своём мире G']['wG_bayes']))
interval('G3 избыток лог-потери', xll, None, 0.012, alt_value=alt['честная формула в своём мире G']['xll'])
interval('G4 xll(G) − xll(GFIX)', xll - xllF, 0.0, None, k=7)
interval('G4 самообман G − GFIX', stat('KELLY_G', lambda r: r['self_dec_snap_mean']) - stat('KELLY_GFIX', lambda r: r['self_dec_snap_mean']), 0.0, None, k=7)
json.dump(out, open(os.path.join(E.HERE, 'pilot', 'pilot_calib.json'), 'w'), ensure_ascii=False, indent=1, default=float)
