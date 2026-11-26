#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCSHIFT-01: мощность до прогона → OUT_DIR/power.json. python3 power_ocshift.py OUT_DIR
Основа — прогон правил зарегистрированным кодом на трёх готовых сдвигах как на средах (пост-хок; опорой не считается):
  chain_old_test.json  — части test (6297 задач): точечные эффекты;
  chain_old_pilot.json — части pilot (2699 задач): разброс бутстрепа и расстояния до границ по правилу вердикта.
Правило вердикта (совет 60, п. 4а–4б) — три интервала вместе: BC, процентильный и обратный; порог с каждой стороны — расстояние
от точки до дальней из трёх границ (урок № 161). У R2 на стороне «подтверждено» — ещё нормальная граница z·SE (п. 3).
Пересчёт на опыт: 10 сред по 2200 задач. Стандартная ошибка среднего по средам:
  SE = √(средняя по трём сдвигам дисперсия разности в среде · n_прежн / n_нов) / √10,
  n — число задач OOD (R1, R3) или ID (R2). Порог — расстояние до дальней границы в единицах SE прогона по трём сдвигам,
  умноженное на SE опыта. Эффект — среднее по трём сдвигам, ужатое вдвое. Мощность — в сторону знака эффекта: Φ((|эффект| − порог) / SE).
Предохранитель «без одного диапазона» (п. 5) — счёт Монте-Карло (зерно 7 650 000, 400 000 розыгрышей): пять диапазонов по две
  среды; истинные эффекты сред — эффект вдвое плюс отклонение диапазона (общее для двух его сред — худший случай для
  предохранителя), отклонения центрированы, чтобы среднее по десяти средам равнялось эффекту; оценка среды — плюс шум среды.
  Разброс между диапазонами τ — по трём готовым сдвигам (дисперсия точек минус средняя дисперсия оценки), два случая: τ как
  есть и τ вдвое. В таблицу и в вес идёт меньшая из мощностей с предохранителем.
Вес (совет 60, п. 6): log₂(min(мощность, ожидание из PREREG §7) / LEVEL); при значении не выше LEVEL — 0. Мощность перенесена
  с готовых сдвигов (другой режим), поэтому ожидание — её потолок.
Строгая ветвь (п. 4в): вывод невозможен, если граница BC на стороне вывода за разрешением повторов; строка strict показывает,
  было ли так на готовых сдвигах.
R4 (неоднородность): разброс между средами τ — по трём сдвигам, ужат вдвое; мощность ≈ P(χ²(m−1) > крит / (1 + τ² / s²)),
  s — ст. отклонение разности в среде опыта. Это оценка: сдвигов три."""
import json
import os
import sys
from math import erf, log2, sqrt

import numpy as np
from scipy.stats import chi2, norm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_ocshift_test as A  # noqa: E402

Phi = lambda z: 0.5 * (1 + erf(z / sqrt(2)))          # noqa: E731
M_ENVS, N_ID, N_OOD = 10, 1000.0, 1200.0               # раскладка теста: 10 сред; в среде в среднем около 1000 задач ID и 1200 OOD
N_SIM, SEED_SIM = 400_000, 7_650_000
# Ожидания из PREREG §7 для стороны ожидаемого знака (копия; потолок мощности в весе, совет 60, п. 6).
EXPECT = {'R1': ('E1', 0.40), 'R2': ('E3', 0.88), 'R3': ('E5', 0.28), 'R4': ('E6', 0.55)}


def guard_power(mu, thr, s_env, tau, n=N_SIM, seed=SEED_SIM):
    """Доля розыгрышей «вывод по порогу» и «вывод, и знак среднего сохраняется без любого одного диапазона»."""
    g = np.random.default_rng(seed)
    r = g.normal(0.0, tau, (n, 5)) if tau > 0 else np.zeros((n, 5))
    r -= r.mean(1, keepdims=True)                                         # среднее истинных эффектов по десяти средам равно mu
    d = mu + np.repeat(r, 2, axis=1) + g.normal(0.0, s_env, (n, 10))
    sgn = 1.0 if mu > 0 else -1.0
    concl = sgn * d.mean(1) > thr
    loo = (d.sum(1, keepdims=True) - d.reshape(n, 5, 2).sum(2)) / 8.0     # среднее без диапазона
    holds = (sgn * loo > 0).all(1)
    return dict(tau=float(tau), power=float(concl.mean()), power_guard=float((concl & holds).mean()), guard_holds=float(holds.mean()))


def weight(power, key):
    name, e = EXPECT[key]
    p = min(power, e)
    return dict(power_for_weight=power, expectation=e, expectation_id=name, capped=p, weight_bits=log2(p / A.LEVEL) if p > A.LEVEL else 0.0,
                note='мощность перенесена с готовых сдвигов (другой режим); потолок — ожидание из PREREG §7')


def main(out_dir, n_id=N_ID, n_ood=N_OOD):
    ct = json.load(open(os.path.join(out_dir, 'chain_old_test.json'), encoding='utf-8'))
    cp = json.load(open(os.path.join(out_dir, 'chain_old_pilot.json'), encoding='utf-8'))
    envs = cp['method']['valid']
    zl = float(norm.ppf(1 - A.LEVEL))
    keys = [k for k, _ in A.IV]
    out = dict(level=A.LEVEL, m_envs=M_ENVS, n_id_env=n_id, n_ood_env=n_ood, shifts=envs, chain_B=dict(pilot=cp['B'], test=ct['B']),
               note='пост-хок по трём готовым сдвигам; эффект ужат вдвое; порог — по правилу вердикта (дальняя из границ BC, процентильной '
                    'и обратной; у R2 — ещё нормальная граница); мощность — с предохранителем «без одного диапазона», худший из случаев τ')
    for k in ('R1', 'R2', 'R3'):
        eff = [ct['envs'][n]['rules_env'][k]['point'] for n in envs]
        d = float(np.mean(eff))
        nk = 'n_id' if k == 'R2' else 'n_ood'
        var = float(np.mean([cp['envs'][n]['rules_env'][k]['sd'] ** 2 * cp['envs'][n][nk] / (n_id if k == 'R2' else n_ood) for n in envs]))
        se = sqrt(var / M_ENVS)
        c = cp[k]
        sd_chain = sqrt(float(np.mean([cp['envs'][n]['rules_env'][k]['sd'] ** 2 for n in envs])) / len(envs))
        dist_lo = {key: (c['delta'] - c[key][0]) / sd_chain for key in keys}
        dist_hi = {key: (c[key][1] - c['delta']) / sd_chain for key in keys}
        if k == 'R2':
            dist_hi['normal'] = zl                                        # нормальная граница: точка + z·SE (SE прогона = sd_chain)
        lo_k, hi_k = max(dist_lo.values()), max(dist_hi.values())
        side = 1 if d < 0 else 0
        thr = (hi_k if d < 0 else lo_k) * se
        p_full, p_half = Phi((abs(d) - thr) / se), Phi((abs(d) / 2 - thr) / se)
        s_old2 = float(np.mean([ct['envs'][n]['rules_env'][k]['sd'] ** 2 for n in envs]))
        tau = sqrt(max(0.0, float(np.var(eff, ddof=1)) - s_old2))
        sims = [guard_power(d / 2, thr, sqrt(var), t) for t in (tau, tau / 2)]
        p_guard = min(s['power_guard'] for s in sims)
        und = dict(pilot=bool(cp[k]['bc_undetermined'][side]), test=bool(ct[k]['bc_undetermined'][side]))
        out[k] = dict(effect_by_shift=eff, effect=d, effect_half=d / 2, expected_sign='минус' if d < 0 else 'плюс',
                      sd_env=sqrt(var), se_mean=se,
                      chain=dict(z0=c['z0'], sd_mean=sd_chain, lower_k=lo_k, upper_k=hi_k, lower_by_interval=dist_lo, upper_by_interval=dist_hi,
                                 binding=max((dist_hi if d < 0 else dist_lo).items(), key=lambda t: t[1])[0], verdict=c['verdict'],
                                 verdict_strict=c['verdict_strict'], verdict_test_parts=ct[k]['verdict'], verdict_strict_test_parts=ct[k]['verdict_strict'],
                                 z0_test_parts=ct[k]['z0']),
                      threshold=thr, power={'по трём сдвигам': p_full, 'ужатый вдвое': p_half}, tau_between_shifts=tau,
                      guard=dict(simulations=sims, power_half_with_guard=p_guard, cost=p_half - p_guard,
                                 note='пять диапазонов по две среды; отклонение диапазона общее для его сред; τ как есть и вдвое; берётся меньшее'),
                      strict=dict(bc_undetermined_on_verdict_side=und, power_half={w: (0.0 if u else p_guard) for w, u in und.items()},
                                  note='строгая ветвь: при границе BC за разрешением повторов вывод невозможен при любом эффекте'),
                      mde_power08=thr + 0.8416 * se, reading_power=p_guard, **weight(p_guard, k))
    d3 = np.array(out['R3']['effect_by_shift'])
    s_old2 = float(np.mean([ct['envs'][n]['rules_env']['R3']['sd'] ** 2 for n in envs]))
    tau2 = max(0.0, float(d3.var(ddof=1)) - s_old2)
    s_new2 = out['R3']['sd_env'] ** 2
    crit = float(chi2.ppf(1 - A.LEVEL, M_ENVS - 1))
    pw = lambda t2: float(chi2.sf(crit / (1 + t2 / s_new2), M_ENVS - 1))    # noqa: E731
    out['R4'] = dict(tau=sqrt(tau2), tau_half=sqrt(tau2) / 2, sd_env=sqrt(s_new2), chi2_crit=crit, df=M_ENVS - 1,
                     power={'по трём сдвигам': pw(tau2), 'ужатый вдвое': pw(tau2 / 4)}, reading_power=pw(tau2 / 4), **weight(pw(tau2 / 4), 'R4'),
                     chain=dict(Q=cp['R4'].get('Q'), p_chi2=cp['R4'].get('p_chi2'), p_boot=cp['R4'].get('p_boot')),
                     note_r4='оценка: три сдвига; случайные эффекты с равной дисперсией оценки в средах')
    sides = 7                                                             # R1–R3 по две стороны, у R4 одна
    out['series_false_level'] = dict(confirmed=A.LEVEL * 4, any_sign=A.LEVEL * sides, sides=sides)
    json.dump(out, open(os.path.join(out_dir, 'power.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == '__main__':
    main(sys.argv[1])
