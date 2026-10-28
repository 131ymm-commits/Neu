#!/usr/bin/env python3
"""TRUST-04: калибровка предсказаний по пилоту v2 для 20 тестовых зёрен (после второй проверки по трём линзам).
Вход: pilot/v2/results_trust_04_A.json и _B.json (зёрна 1100–1109, нынешний код); независимая реализация —
indep/pilot (1200–1204) и indep/pilot1205 (1205–1209). Выход: pilot/v2/pilot_calib2.json и печать.

Метод:
  знаковые и интервальные — значение на зерне ~ N(среднее, SD) пилота; счёт из 20 — биномиальный; мощность — при SD пилота
  и при SD × 1,5; ложный уровень — на границе (истинное среднее на кромке интервала или P(a < b) = ½): P(Bin(20; ½) ≥ k)
  (правка 4 второй проверки; так же считается и знаковый тест);
  выбор k: наибольший k из 15…18, при котором мощность при SD × 1,5 ≥ 0,9; если такого нет — наибольший k из 14…18 с
  мощностью ≥ 0,9 при SD пилота (с пометкой «запас мал»);
  A15 (DEMES_NOWITHIN) — смесь: со срывом (SD w_G между группами > 0,5 в среднем по окну; как Д2 TRUST-03) значение вне
  интервала, без срыва — N(среднее, SD) зёрен без срыва; доля срывов q — по пилоту и «пессимистично» q = 0,2 при SD × 1,5;
  эквивалентность (TOST Шуирмана по ДИ Уэлча уровня 90 % или 95 %, граница ±0,1 по u) — доля из 20 000 симуляций по
  20 значений из N пилота, где ДИ внутри (−0,1; 0,1); ложный уровень — то же при истинной разности 0,1;
  вес сводного — log₂(мощность / ложный уровень), ложный уровень сводного — наибольший у частей, мощность — произведение.
Запуск из папки опыта: python3 pilot/v2/pilot_calib2.py > pilot/v2/pilot_calib2.log"""
import json
import math
import os
import sys

import numpy as np
from scipy.stats import binom, levene, norm, spearmanr
from scipy.stats import t as tdist

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, EXP)
import exp_trust_04 as E  # noqa: E402

FROZEN = {'base': (0.9873, 0.6891), 'r075': (0.5768, 0.3897), 'r095': (1.7134, 1.1968), 'b03': (1.2221, 0.9622),
          'b09': (0.8328, 0.5372)}
N, DELTA, NSIM, BREAK_SD = 20, 0.1, 20000, 0.5
runs = []
for part in ('A', 'B'):
    d = json.load(open(os.path.join(HERE, f'results_trust_04_{part}.json')))
    assert d['params']['part'] == part and d['params']['SEEDS'] == E.PILOT_SEEDS
    runs += d['runs']
F = {(r['seed'], r['arm']): r['final'] for r in runs}
seeds = E.PILOT_SEEDS
assert all((s, a) in F for s in seeds for a in E.ARMS), 'пилот v2 неполный'


def u(a):
    my, far = FROZEN[E.ARMS[a]['world']]
    return np.array([(F[(s, a)]['wG'] - far) / (my - far) for s in seeds])


col = lambda a, k: np.array([F[(s, a)][k] for s in seeds])
f_bound = lambda k, n=N: float(1 - binom.cdf(k - 1, n, 0.5))
P_atleast = lambda p, k, n=N: float(1 - binom.cdf(k - 1, n, p))
p_in = lambda mu, sd, lo, hi: float(norm.cdf((hi - mu) / sd) - norm.cdf((lo - mu) / sd))
KS = (15, 16, 17, 18)
out = {}


def choose_k(pw, pw15):
    ok = [k for k in KS if pw15[k] >= 0.9]
    if ok:
        return max(ok), ''
    ok = [k for k in (14,) + KS if pw[k] >= 0.9]
    return (max(ok), 'запас мал') if ok else (14, 'мощность < 0,9 при любом k')


def counted(name, kind, p1, p15, extra):
    pw = {k: P_atleast(p1, k) for k in (14,) + KS}; pw15 = {k: P_atleast(p15, k) for k in (14,) + KS}
    k, flag = choose_k(pw, pw15)
    out[name] = dict(kind=kind, p_seed=p1, p_seed_sd15=p15, power_by_k=pw, power_sd15_by_k=pw15, k=k, flag=flag,
                     power=pw[k], power_sd15=pw15[k], false_level=f_bound(k), **extra)


def interval(name, a, lo, hi):
    x = u(a); mu, sd = float(x.mean()), float(x.std(ddof=1))
    counted(name, 'интервал', p_in(mu, sd, lo, hi), p_in(mu, 1.5 * sd, lo, hi),
            dict(arm=a, interval=[lo, hi], mean=mu, sd=sd, pilot_count=int(np.sum((x >= lo) & (x <= hi))), values=x.round(4).tolist()))


def sign(name, a, b, key='wG'):
    d = col(a, key) - col(b, key); mu, sd = float(d.mean()), float(d.std(ddof=1))
    counted(name, 'знак', float(norm.cdf(-mu / sd)), float(norm.cdf(-mu / (1.5 * sd))),
            dict(pair=[a, b], mean=mu, sd=sd, pilot_count=int(np.sum(d < 0)), values=d.round(4).tolist()))


def tost_rate(mx, sx, my, sy, level, nx=N, ny=N, delta=DELTA, nsim=NSIM, seed=0):
    g = np.random.default_rng(seed)
    x = g.normal(mx, sx, (nsim, nx)); y = g.normal(my, sy, (nsim, ny))
    vx, vy = x.var(1, ddof=1) / nx, y.var(1, ddof=1) / ny; se = np.sqrt(vx + vy)
    df = (vx + vy) ** 2 / (vx ** 2 / (nx - 1) + vy ** 2 / (ny - 1)); h = tdist.ppf(1 - (1 - level) / 2, df) * se
    dd = x.mean(1) - y.mean(1)
    return float(np.mean((dd - h > -delta) & (dd + h < delta)))


def equiv(name, x, y, **extra):
    mx, sx, my, sy = float(x.mean()), float(x.std(ddof=1)), float(y.mean()), float(y.std(ddof=1))
    r = dict(kind='эквивалентность', diff=mx - my, sd_x=sx, sd_y=sy, delta=DELTA, **extra)
    for lev in (0.90, 0.95):
        r[f'power_{int(lev * 100)}'] = tost_rate(mx, sx, my, sy, lev)
        r[f'power_sd15_{int(lev * 100)}'] = tost_rate(mx, 1.5 * sx, my, 1.5 * sy, lev, seed=1)
        r[f'false_level_{int(lev * 100)}'] = tost_rate(my + DELTA, sx, my, sy, lev, seed=2)
    out[name] = r


# ---- блок А ----
interval('A1', 'POOLED', -1 / 6, 1 / 6); interval('A2', 'POOLED_FREE', -1 / 6, 1 / 6)
interval('A3', 'DEMES', 1 / 6, 5 / 6); interval('A4', 'DEMES_FREE', 1 / 6, 5 / 6)
sign('A5', 'POOLED', 'DEMES'); sign('A6', 'POOLED_FREE', 'DEMES_FREE')
equiv('A7', u('POOLED'), u('POOLED_FREE')); equiv('A8', u('DEMES'), u('DEMES_FREE'))
interval('A9', 'DEMES_NOSEL', 2 / 3, 4 / 3); interval('A10', 'DEMES_NOSEL_FREE', 2 / 3, 4 / 3)
interval('A11', 'COUNCIL_SIGN', -1 / 3, 1 / 3); equiv('A12', u('COUNCIL'), u('COUNCIL_SIGN'))
interval('A13', 'COUNCIL', -1 / 6, 1 / 6); interval('A14', 'MYOPIC', 2 / 3, 4 / 3)
# A15: DEMES_NOWITHIN, смесь «срыв / без срыва»
xw = u('DEMES_NOWITHIN'); brk = col('DEMES_NOWITHIN', 'wG_sd_groups') > BREAK_SD; q = float(brk.mean())
xnb = xw[~brk]; mu_nb, sd_nb = float(xnb.mean()), float(xnb.std(ddof=1))
p1 = (1 - q) * p_in(mu_nb, sd_nb, -1 / 6, 1 / 6); p15 = (1 - max(q, 0.2)) * p_in(mu_nb, 1.5 * sd_nb, -1 / 6, 1 / 6)
counted('A15', 'интервал (срывы)', p1, p15, dict(arm='DEMES_NOWITHIN', interval=[-1 / 6, 1 / 6], breakdowns=int(brk.sum()),
                                               q=q, q_pessimistic=max(q, 0.2), mean_nb=mu_nb, sd_nb=sd_nb,
                                               pilot_count=int(np.sum(np.abs(xw) <= 1 / 6)), values=xw.round(4).tolist(),
                                               sd_groups=col('DEMES_NOWITHIN', 'wG_sd_groups').round(4).tolist()))
interval('A16', 'DEMES_GPOOL', 1 / 6, 5 / 6); equiv('A17', u('DEMES_GPOOL'), u('DEMES_FREE'))
sign('A18', 'POOLED_FREE', 'DEMES_GPOOL')
# ---- блок Б ----
for i, c in enumerate(('r075', 'r095', 'b03', 'b09', 'IND', 'MIG', 'SIG5')):
    sign(f'B{i + 1}', f'POOLED_{c}', f'DEMES_{c}')
for i, w in enumerate(('r075', 'r095', 'b03', 'b09')):
    interval(f'B{i + 8}', f'POOLED_{w}', -1 / 3, 1 / 3); interval(f'B{i + 12}', f'MYOPIC_{w}', 2 / 3, 4 / 3)
# ---- блок В: независимая реализация, пилот 1200–1209 (10 зёрен), u — по FROZEN ----
ir = []
for sub in ('pilot', 'pilot1205'):
    p = os.path.join(EXP, 'indep', sub, 'results_indep_04.json')
    d = json.load(open(p)); assert d['complete'] and d['meta']['noise_convention'] == 'sd'; ir += d['runs']
my0, far0 = FROZEN['base']
UI = {a: np.array([(r['w_G'] - far0) / (my0 - far0) for r in sorted(ir, key=lambda r: r['seed']) if r['arm'] == a])
      for a in ('MYOPIC', 'DEMES', 'POOLED', 'COUNCIL')}
assert all(len(v) == 10 for v in UI.values()), {a: len(v) for a, v in UI.items()}
for a in ('MYOPIC', 'DEMES', 'POOLED', 'COUNCIL'):
    equiv(f'C_{a}', UI[a], u(a), n_indep_pilot=len(UI[a]), u_indep=UI[a].round(4).tolist())
dp = UI['POOLED'] - UI['DEMES']; mu, sd = float(dp.mean()), float(dp.std(ddof=1))
counted('C_ORDER', 'знак', float(norm.cdf(-mu / sd)), float(norm.cdf(-mu / (1.5 * sd))), dict(mean=mu, sd=sd, pilot_count=int(np.sum(dp < 0))))
# ---- разведка ----
EXPL = {}


def sign_x(name, a, b, k=15):
    d = col(a, 'wG') - col(b, 'wG'); mu, sd = float(d.mean()), float(d.std(ddof=1))
    EXPL[name] = dict(kind='знак', pair=[a, b], k=k, mean=mu, sd=sd, power=P_atleast(float(norm.cdf(-mu / sd)), k),
                      power_sd15=P_atleast(float(norm.cdf(-mu / (1.5 * sd))), k), false_level=f_bound(k), pilot_count=int(np.sum(d < 0)))


def bf_rate(sa, sb, nsim=4000, seed=3):
    """Мощность одностороннего теста Брауна–Форсайта (levene, center='median'), SD a > SD b, уровень 0,05; n = 20 у обеих."""
    g = np.random.default_rng(seed); hit = 0
    for _ in range(nsim):
        xa, xb = g.normal(0, sa, N), g.normal(0, sb, N)
        p = levene(xa, xb, center='median').pvalue
        hit += (xa.std(ddof=1) > xb.std(ddof=1)) and (p / 2 < 0.05)
    return hit / nsim


sa, sb = float(u('POOLED_IND').std(ddof=1)), float(u('POOLED').std(ddof=1))
EXPL['EB1'] = dict(kind='разброс (Браун–Форсайт)', sd_IND=sa, sd_base=sb, ratio=sa / sb, power=bf_rate(sa, sb),
                   power_sd15=bf_rate(sa / 1.5, sb), false_level=bf_rate(sb, sb, seed=4))
equiv('EB2', u('POOLED_MIG'), u('POOLED')); EXPL['EB2'] = out.pop('EB2')
sign_x('EB3', 'DEMES', 'DEMES_MIG'); sign_x('EB4', 'DEMES', 'DEMES_SIG5')
for w in ('r075', 'r095', 'b03', 'b09'):
    equiv(f'EB5_{w}', u(f'DEMES_{w}'), u('DEMES')); EXPL[f'EB5_{w}'] = out.pop(f'EB5_{w}')
E1_ARMS = ['DEMES', 'DEMES_FREE', 'DEMES_GPOOL', 'DEMES_IND', 'DEMES_MIG', 'DEMES_SIG5', 'DEMES_r075', 'DEMES_r095', 'DEMES_b03', 'DEMES_b09']
ub = np.array([u(a).mean() for a in E1_ARMS]); Rb = np.array([col(a, 'V_between').mean() / (col(a, 'V_between').mean() + col(a, 'V_within').mean()) for a in E1_ARMS])
rho = spearmanr(ub, 1 - Rb)
EXPL['EB6'] = dict(kind='u ≈ 1 − R', arms=E1_ARMS, u=ub.round(4).tolist(), one_minus_R=(1 - Rb).round(4).tolist(),
                   abs_gap=np.abs(ub - (1 - Rb)).round(4).tolist(), n_within_01=int(np.sum(np.abs(ub - (1 - Rb)) <= 0.1)),
                   spearman=float(rho.statistic), spearman_p_two_sided=float(rho.pvalue))
# ---- описательное ----
DESC = {a: dict(u_mean=float(u(a).mean()), u_sd=float(u(a).std(ddof=1)), step_sd=float(col(a, 'step_sd').mean()),
                R=float(col(a, 'V_between').mean() / max(col(a, 'V_between').mean() + col(a, 'V_within').mean(), 1e-300)),
                V_between=float(col(a, 'V_between').mean()), V_within=float(col(a, 'V_within').mean()),
                sd_groups=float(col(a, 'wG_sd_groups').mean()), n_break=int(np.sum(col(a, 'wG_sd_groups') > BREAK_SD)),
                price_within=float(col(a, 'price_within').mean()), logloss=float(col(a, 'logloss').mean())) for a in E.ARMS}
# ---- сводные и семья ----
COMPOSITES = dict(SA=['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8'], SA2=['A11', 'A12'],
                  SA3=['A2', 'A4', 'A15', 'A16', 'A17', 'A18'], SB=[f'B{i}' for i in range(1, 8)],
                  SB2=[f'B{i}' for i in range(8, 12)], SC=['C_MYOPIC', 'C_DEMES', 'C_POOLED', 'C_COUNCIL', 'C_ORDER'])
bits = {}
for lev in (90, 95):
    fl = lambda p: out[p]['false_level'] if 'false_level' in out[p] else out[p][f'false_level_{lev}']
    pw = lambda p, s='': out[p][f'power{s}'] if 'false_level' in out[p] else out[p][f'power{s}_{lev}']
    bits[lev] = {}
    for c, parts in COMPOSITES.items():
        f = max(fl(p) for p in parts); P = float(np.prod([pw(p) for p in parts])); P15 = float(np.prod([pw(p, '_sd15') for p in parts]))
        bits[lev][c] = dict(false_level=f, power=P, power_sd15=P15, bits=math.log2(P / f))
    bits[lev]['family_sum_parts'] = float(sum(fl(p) for p in out))
    bits[lev]['family_sum_composites'] = float(sum(bits[lev][c]['false_level'] for c in COMPOSITES))
    bits[lev]['expl_sum'] = float(sum(v['false_level'] if 'false_level' in v else v.get(f'false_level_{lev}', 0.0)
                                      for k, v in EXPL.items() if k != 'EB6'))
json.dump(dict(confirm=out, explore=EXPL, desc=DESC, composites=COMPOSITES, bits=bits, N=N, seeds=seeds),
          open(os.path.join(HERE, 'pilot_calib2.json'), 'w'), ensure_ascii=False, indent=1)
# ---- печать ----
for k, v in out.items():
    if v['kind'] == 'эквивалентность':
        print(f"{k:8s} экв.  разн. {v['diff']:+.4f}  SD {v['sd_x']:.4f}/{v['sd_y']:.4f}  мощн. 90 % {v['power_90']:.3f} ({v['power_sd15_90']:.3f})"
              f"  95 % {v['power_95']:.3f} ({v['power_sd15_95']:.3f})  ложн. {v['false_level_90']:.4f}/{v['false_level_95']:.4f}")
    else:
        print(f"{k:8s} {v['kind'][:9]:9s} p на зерне {v['p_seed']:.4f} ({v['p_seed_sd15']:.4f})  k = {v['k']}  мощн. {v['power']:.3f}"
              f" ({v['power_sd15']:.3f})  ложн. {v['false_level']:.4g}  пилот {v['pilot_count']}/10 {v['flag']}")
for k, v in EXPL.items():
    print(k, {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk not in ('values',)})
for lev in (90, 95):
    print(f'ДИ эквивалентности {lev} %:', {c: (round(b['false_level'], 4), round(b['power'], 3), round(b['power_sd15'], 3), round(b['bits'], 2))
                                           for c, b in bits[lev].items() if isinstance(b, dict)},
          'семья: части', round(bits[lev]['family_sum_parts'], 4), 'сводные', round(bits[lev]['family_sum_composites'], 4),
          'разведка', round(bits[lev]['expl_sum'], 4))
for a, v in DESC.items():
    print(f"  {a:18s} u {v['u_mean']:+.4f} ± {v['u_sd']:.4f}  шаг {v['step_sd']:.4f}  R {v['R']:.3f}  Vb {v['V_between']:.5f}"
          f"  Vw {v['V_within']:.5f}  SD групп {v['sd_groups']:.3f}  срывов {v['n_break']}  Прайс внутр. {v['price_within']:+.5f}  ll {v['logloss']:.4f}")
