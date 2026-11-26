#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-05: числа PREREG — только из json пилота (ERRORS № 200, 226). Правило активности — PREREG-DISTILL-02 §5 п. 1 (сверено по
тексту, урок ERRORS № 231): правило решающее, если решающая мощность («больше» + «меньше», двусторонние правила) не меньше 0,2 и при τ
пилота, и при τ из верхней границы (дисперсия точек сред — верхняя граница 97,5 % по χ², минус s²). Мощность — scales_d5.power (модель
«новая среда», 8 сред теста). Ожидания — 0,95 × мощность ожидаемой стороны при τ пилота, при τ из верхней границы — рядом. Вес —
log₂(мощность стороны / уровень). Замок — сверка с scales_d5.RULES_ACTIVE.
  python3 prereg_numbers_d5.py [--write]"""
import json
import math
import os
import sys

import numpy as np
from scipy.stats import chi2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import scales_d5 as S  # noqa: E402

P = os.path.join(ROOT, 'gha_out/distill05_pilot/pilot.json')
POWER_MIN = 0.2
SHORT = {'Falcon3-1B-Instruct': 'Falcon 1B', 'OLMo-2-0425-1B-Instruct': 'OLMo 1B', 'Qwen2.5-0.5B-Instruct': 'Qwen 0,5B',
         'Qwen2.5-1.5B-Instruct': 'Qwen 1,5B', 'SmolLM2-1.7B-Instruct': 'SmolLM 1,7B', 'SmolLM2-360M-Instruct': 'SmolLM 360M',
         'TinyLlama-1.1B-Chat-v1.0': 'TinyLlama 1,1B'}


def r(x, n=4, sign=False):
    s = f'{x:+.{n}f}' if sign else f'{x:.{n}f}'
    return s.replace('-', '−').replace('.', ',')


def power_at(mu, tau, s, m, level, seed):
    g = np.random.default_rng(seed)
    X = g.normal(mu, math.sqrt(tau ** 2 + s ** 2), size=(200_000, m))
    mean, sd = X.mean(1), X.std(1, ddof=1)
    from scipy.stats import norm, t as st
    h = norm.ppf(1 - level) * s / math.sqrt(m)
    tt = mean / (sd / math.sqrt(m))
    crit = st.ppf(1 - level, m - 1)
    return float(((mean - h > 0) & (tt > crit)).mean()), float(((mean + h < 0) & (tt < -crit)).mean())


def main(a):
    p = json.load(open(P, encoding='utf-8'))
    envs = p['envs']
    m = len(S.TEST_ENVS)
    print('## Пилот (уже виденные пятизначные суммы): точки сред — Δ = доля сотен − доля десятков; Р2 — сотни OLMo − среднее сотен шести')
    print('| среда | ' + ' | '.join(SHORT[h] for h in S.HEADS) + ' | Р2 |')
    print('|---|' + '---|' * (len(S.HEADS) + 1))
    for k, e in envs.items():
        print(f"| {e['env']} ({k.split(':')[0]}) | " + ' | '.join(r(e['delta'][h], 3, True) if h in e['delta'] and math.isfinite(e['delta'][h]) else '—'
                                                          for h in S.HEADS) + f" | {r(e['contrast'], 3, True)} |")
    print('## Доли масштабов «прочих» у OLMo по средам пилота (1 / 10 / 100)')
    for k, e in envs.items():
        sh = e['shares'][S.OLMO]
        print(f"- {e['env']} ({k.split(':')[0]}): {r(sh['0'], 3)} / {r(sh['1'], 3)} / {r(sh['2'], 3)}; «прочих» {sh['n_other']}")
    rules, act = {}, {}
    print('## Мощность для 8 сред теста и правило активности')
    for key in [f'Р1:{h}' for h in S.HEADS] + ['Р2']:
        e = p['power'][key]
        pts = [float(v['contrast']) if key == 'Р2' else float(v['delta'][key[3:]]) for v in envs.values()
               if (key == 'Р2' or key[3:] in v['delta'])]
        pts = [x for x in pts if math.isfinite(x)]
        n = len(pts)
        var_hi = (n - 1) * float(np.var(pts, ddof=1)) / float(chi2.ppf(0.025, n - 1))
        tau_hi = math.sqrt(max(0.0, var_hi - e['s'] ** 2))
        level = S.level_of(key)
        more, less = power_at(e['mu'], e['tau'], e['s'], m, level, S.SEED + 8)       # уровень правила (S.level_of); μ, τ, s — из пилота
        more_hi, less_hi = power_at(e['mu'], tau_hi, e['s'], m, level, S.SEED + 8)
        e = dict(e, more=more, less=less, decisive=more + less)
        dec, dec_hi = e['decisive'], more_hi + less_hi
        act[key] = dec >= POWER_MIN and dec_hi >= POWER_MIN
        side = 'less' if e['less'] >= e['more'] else 'more'
        p_side = e[side]
        rules[key] = dict(mu=e['mu'], tau=e['tau'], tau_hi=tau_hi, s=e['s'], n_envs=e['n_envs'], level=level, more=e['more'], less=e['less'],
                          decisive=dec, more_tau_hi=more_hi, less_tau_hi=less_hi, decisive_tau_hi=dec_hi, active=act[key],
                          expect_outcome='меньше' if side == 'less' else 'больше', expect=round(0.95 * p_side, 4),
                          expect_tau_hi=round(0.95 * (less_hi if side == 'less' else more_hi), 4),
                          bits_side=round(math.log2(max(p_side, 1e-12) / level), 2),
                          bits_side_tau_hi=round(math.log2(max(less_hi if side == 'less' else more_hi, 1e-12) / level), 2),
                          p_mean_side=float(__import__('scipy.stats', fromlist=['norm']).norm.cdf(abs(e['mu']) / math.sqrt((e['tau'] ** 2 + e['s'] ** 2) / m))),
                          bits_not=round(math.log2((1 - min(dec, 1 - 1e-12)) / (1 - 2 * level)), 2))
        x = rules[key]
        name = 'Р2 (контраст)' if key == 'Р2' else f'Р1 {SHORT[key[3:]]}'
        print(f"- {name}: μ {r(x['mu'], 4, True)}, τ {r(x['tau'], 4)} (верхняя {r(tau_hi, 4)}), s {r(x['s'], 4)}, сред пилота {x['n_envs']}, уровень "
              f"{r(level, 6)}; «больше» {r(x['more'], 4)}, «меньше» {r(x['less'], 4)} → решающая {r(dec, 4)}; при τ из верхней границы "
              f"{r(more_hi, 4)} / {r(less_hi, 4)} → {r(dec_hi, 4)} → {'решающее' if act[key] else 'описательно'}; ожидание «{x['expect_outcome']}» "
              f"{r(x['expect'], 4)} (при τ из верхней границы {r(x['expect_tau_hi'], 4)}); вес исхода {r(x['bits_side'], 2, True)} бит (при τ из верхней "
              f"границы {r(x['bits_side_tau_hi'], 2, True)}); P(среднее 8 сред по ту же сторону от нуля) {r(x['p_mean_side'], 4)}")
    ok = S.RULES_ACTIVE is not None and all(bool(S.RULES_ACTIVE.get(k)) == v for k, v in act.items())
    print('## Замок: scales_d5.RULES_ACTIVE совпадает с правилом активности —', ok)
    n_dec = sum(act.values())
    fw = sum(2 * rules[k]['level'] for k in act if act[k])
    print(f'- решающих правил: {n_dec}; ложный решающий вердикт в серии — не больше {r(fw, 4)} (Бонферрони, обе стороны)')
    if '--write' in a:
        json.dump(dict(rule='0,95 × мощность ожидаемой стороны при τ пилота (DISTILL-02 §6); правило активности — DISTILL-02 §5 п. 1',
                       power_min=POWER_MIN, level=S.LEVEL, level_six=S.LEVEL / 6, pilot='gha_out/distill05_pilot/pilot.json', rules=rules,
                       active=act, fwer=fw), open(os.path.join(HERE, 'expect_d5.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('записано expect_d5.json')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
