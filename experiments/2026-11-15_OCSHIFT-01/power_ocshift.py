#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCSHIFT-01: мощность до прогона → OUT_DIR/power.json. python3 power_ocshift.py OUT_DIR
Основа — прогон правил зарегистрированным кодом на трёх готовых сдвигах как на средах (пост-хок; опорой не считается):
  chain_old_test.json  — части test (6297 задач): точечные эффекты;
  chain_old_pilot.json — части pilot (2699 задач): разброс бутстрепа и расстояния до границ ДИ по правилу вердикта
                          (конъюнкция BC и процентильного — дальняя из двух границ с каждой стороны; урок № 161).
Пересчёт на опыт: 10 сред по 2200 задач. Стандартная ошибка среднего по средам:
  SE = √(средняя по трём сдвигам дисперсия разности в среде · n_прежн / n_нов) / √10,
  n — число задач OOD (R1, R3) или ID (R2). Порог с каждой стороны — расстояние до дальней границы в единицах SE прогона
  по трём сдвигам, умноженное на SE опыта. Эффект — среднее по трём сдвигам, ужатое вдвое.
  Мощность — в сторону знака эффекта: Φ((|эффект| − порог) / SE). Вес — log₂(мощность / LEVEL); при мощности не выше LEVEL — 0.
R4 (неоднородность): разброс между средами τ — по трём сдвигам (дисперсия точек минус средняя дисперсия оценки), ужат вдвое;
  мощность ≈ P(χ²(m−1) > крит / (1 + τ² / s²)), s — ст. отклонение разности в среде опыта. Это оценка: сдвигов три."""
import json
import os
import sys
from math import erf, log2, sqrt

import numpy as np
from scipy.stats import chi2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_ocshift_test as A  # noqa: E402

Phi = lambda z: 0.5 * (1 + erf(z / sqrt(2)))          # noqa: E731
M_ENVS, N_ID, N_OOD = 10, 1000.0, 1200.0               # раскладка теста: 10 сред; в среде в среднем около 1000 задач ID и 1200 OOD


def main(out_dir, n_id=N_ID, n_ood=N_OOD):
    ct = json.load(open(os.path.join(out_dir, 'chain_old_test.json'), encoding='utf-8'))
    cp = json.load(open(os.path.join(out_dir, 'chain_old_pilot.json'), encoding='utf-8'))
    envs = cp['method']['valid']
    out = dict(level=A.LEVEL, m_envs=M_ENVS, n_id_env=n_id, n_ood_env=n_ood, shifts=envs,
               note='пост-хок по трём готовым сдвигам; эффект ужат вдвое; порог — по правилу вердикта (дальняя из границ BC и процентильной)')
    for k in ('R1', 'R2', 'R3'):
        eff = [ct['envs'][n]['rules_env'][k]['point'] for n in envs]
        d = float(np.mean(eff))
        nk = 'n_id' if k == 'R2' else 'n_ood'
        var = float(np.mean([cp['envs'][n]['rules_env'][k]['sd'] ** 2 * cp['envs'][n][nk] / (n_id if k == 'R2' else n_ood) for n in envs]))
        se = sqrt(var / M_ENVS)
        c = cp[k]
        sd_chain = sqrt(float(np.mean([cp['envs'][n]['rules_env'][k]['sd'] ** 2 for n in envs])) / len(envs))
        lo_k = max(c['delta'] - c['ci'][0], c['delta'] - c['ci_percentile'][0]) / sd_chain
        hi_k = max(c['ci'][1] - c['delta'], c['ci_percentile'][1] - c['delta']) / sd_chain
        thr = (hi_k if d < 0 else lo_k) * se
        p_full, p_half = Phi((abs(d) - thr) / se), Phi((abs(d) / 2 - thr) / se)
        out[k] = dict(effect_by_shift=eff, effect=d, effect_half=d / 2, expected_sign='минус' if d < 0 else 'плюс',
                      sd_env=sqrt(var), se_mean=se, chain=dict(z0=c['z0'], sd_mean=sd_chain, lower_k=lo_k, upper_k=hi_k, verdict=c['verdict']),
                      threshold=thr, power={'по трём сдвигам': p_full, 'ужатый вдвое': p_half},
                      mde_power08=thr + 0.8416 * se, weight_bits=log2(p_half / A.LEVEL) if p_half > A.LEVEL else 0.0, reading_power=p_half)
    d3 = np.array(out['R3']['effect_by_shift'])
    s_old2 = float(np.mean([ct['envs'][n]['rules_env']['R3']['sd'] ** 2 for n in envs]))
    tau2 = max(0.0, float(d3.var(ddof=1)) - s_old2)
    s_new2 = out['R3']['sd_env'] ** 2
    crit = float(chi2.ppf(1 - A.LEVEL, M_ENVS - 1))
    pw = lambda t2: float(chi2.sf(crit / (1 + t2 / s_new2), M_ENVS - 1))    # noqa: E731
    out['R4'] = dict(tau=sqrt(tau2), tau_half=sqrt(tau2) / 2, sd_env=sqrt(s_new2), chi2_crit=crit, df=M_ENVS - 1,
                     power={'по трём сдвигам': pw(tau2), 'ужатый вдвое': pw(tau2 / 4)},
                     weight_bits=log2(pw(tau2 / 4) / A.LEVEL) if pw(tau2 / 4) > A.LEVEL else 0.0, reading_power=pw(tau2 / 4),
                     chain=dict(Q=cp['R4'].get('Q'), p_chi2=cp['R4'].get('p_chi2'), p_boot=cp['R4'].get('p_boot')),
                     note='оценка: три сдвига; случайные эффекты с равной дисперсией оценки в средах')
    out['series_false_level'] = A.LEVEL * 4
    json.dump(out, open(os.path.join(out_dir, 'power.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == '__main__':
    main(sys.argv[1])
