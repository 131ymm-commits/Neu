#!/usr/bin/env python3
"""TRUST-02, пост-хок (после проверки отчёта агентом Opus 28.10, 15:35; вердикты не меняет) → posthoc_trust_02.json:
1) избыток лог-потери честной формулы TRUST-01 при b* и при b = 0,6 (в мире, который она сама создаёт);
2) «дальновидный» оптимум: какой вес на источнике G выгоден популяции, если учесть, что источник отвечает на её доверие
   (при каждом весе w_G источник врёт с b = b_of(w_G), остальные 6 весов подбираются под эту ложь по точной лог-потере);
   сравнение с близорукой неподвижной точкой, к которой приходит отбор;
3) KELLY_GFIX (источник не отвечает на доверие) против кромок G1 и G3; вес отбора относительно байесовского при b_final;
4) раздел пар в мире B у KELLY_B; ECE отдельных снимков против ECE усреднённого генотипа.
Запуск из папки опыта: python3 posthoc_trust_02.py"""
import json
import os

import numpy as np
from scipy.optimize import minimize, minimize_scalar

import exp_trust_02 as E

HERE = E.HERE
d = json.load(open(os.path.join(HERE, 'results_trust_02.json')))
a = json.load(open(os.path.join(HERE, 'analysis_trust_02.json')))
seeds = d['params']['SEEDS']
R = {(r['seed'], r['arm']): r for r in d['runs']}
WA, WB, WG, J = E.WA, E.WB, E.WG, 1 + E.G_IDX
out = {}

# 1) честная формула TRUST-01 в мире G
wA = WA.exact_weights()
for tag, b in (('b_star', E.B_STAR), ('own_world_b', E.b_of(wA[J]))):
    w = WG.with_b(b)
    out[f'honest_excess_logloss_{tag}'] = round(w.exact_metrics(wA)['logloss'] - w.exact_metrics(w.exact_weights())['logloss'], 4)
out['honest_own_world_b'] = round(E.b_of(wA[J]), 4)


# 2) дальновидный оптимум (популяция «обязуется» держать вес w_G; источник отвечает на него)
def inner(wg):
    b = E.b_of(wg); w = WG.with_b(b); w_ex = w.exact_weights()
    f = lambda v: w.exact_metrics(np.insert(v, J, wg))['logloss']
    r = minimize(f, np.delete(w_ex, J), method='BFGS', options=dict(gtol=1e-9, maxiter=5000))
    return r.fun, np.insert(r.x, J, wg), b


opt = minimize_scalar(lambda x: inner(x)[0], bounds=(0.2, 1.6), method='bounded', options=dict(xatol=1e-5))
ll_o, w_o, b_o = inner(opt.x)
m_o = WG.with_b(b_o).exact_metrics(w_o)
ws = WG.with_b(E.B_STAR); m_s = ws.exact_metrics(ws.exact_weights())
ll_s_inner = inner(E._W_STAR[J])[0]
out['farsighted'] = dict(wG=round(float(opt.x), 4), share_of_honest=round(float(opt.x) / E.W_REF, 3), bits=round(float(opt.x) / np.log(2), 2),
                         b=round(b_o, 4), logloss=round(ll_o, 4), acc=round(m_o['acc'], 4), self_dec=round(m_o['self_dec'], 4))
out['myopic_fixed_point'] = dict(wG=round(float(E._W_STAR[J]), 4), b=round(E.B_STAR, 4), logloss=round(m_s['logloss'], 4),
                                 acc=round(m_s['acc'], 4), inner_check_logloss=round(ll_s_inner, 4))
out['myopia_cost_logloss'] = round(m_s['logloss'] - ll_o, 4)
out['kelly_G_excess_logloss_mean'] = round(a['verdicts']['G3']['excess_logloss'][0], 4)

# 3) KELLY_GFIX против кромок G1 и G3; вес отбора относительно байесовского при b_final
w_bayes_star = float(E._W_STAR[J])
gfix = [R[(s, 'KELLY_GFIX')] for s in seeds]
out['GFIX_G1_pass'] = int(sum(r['w_final'][J] <= 0.75 * E.W_REF and abs(r['w_final'][J] - w_bayes_star) <= 0.2 for r in gfix))
out['GFIX_G3_pass'] = int(sum(r['excess_logloss_snap_mean'] <= 0.012 for r in gfix))
kg = [R[(s, 'KELLY_G')] for s in seeds]
ratio = [r['w_final'][J] / WG.with_b(r['b_final']).exact_weights()[J] for r in kg]
out['KELLY_G_weight_over_bayes_at_b_final'] = round(float(np.mean(ratio)), 3)
out['KELLY_G_weight_over_honest'] = round(float(np.mean([r['w_final'][J] for r in kg])) / E.W_REF, 3)

# 4) раздел пар в мире B у KELLY_B; ECE снимков против усреднённого генотипа
kb = np.array([R[(s, 'KELLY_B')]['w_final'] for s in seeds]).mean(0)
wBx = WB.exact_weights()
out['B_pair_split_KELLY'] = dict(src_r07=round(float(kb[2]), 3), copy_r07=round(float(kb[5]), 3), exact_r07=round(float(wBx[2]), 4),
                                 src_r09=round(float(kb[4]), 3), copy_r09=round(float(kb[6]), 3), exact_r09=round(float(wBx[4]), 4))
out['ece_snap_vs_window'] = {arm: dict(window=round(float(np.mean([R[(s, arm)]['exact']['ece'] for s in seeds])), 4),
                                       snap=round(float(np.mean([R[(s, arm)]['ece_snap_mean'] for s in seeds])), 4))
                             for arm in E.ARMS}
out['contest_excess_logloss_snap'] = {arm: round(float(np.mean([R[(s, arm)]['excess_logloss_snap_mean'] for s in seeds])), 4)
                                      for arm in ('CONTEST_A', 'CONTEST400_A')}
out['contest_ratios'] = dict(self_dec=round(a['verdicts']['M2']['ratio'], 3),
                             excess_logloss=round(out['contest_excess_logloss_snap']['CONTEST400_A'] / out['contest_excess_logloss_snap']['CONTEST_A'], 3))
json.dump(out, open(os.path.join(HERE, 'posthoc_trust_02.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
