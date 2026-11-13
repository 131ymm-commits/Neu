#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-01R: мощность до прогона (решение совета 43) → power_r.json.
Функции — из ../2026-11-12_PLATON-01/power_platon.py и platon_analyze.py (код не меняется).
Сценарии (доли PLATON-01, run/results_platon01.json):
  наблюдённый — FC ZS 0, ZN 0; TC TS 1,0, TN 0,6; FC ZSF 0,45, ZNF 0,1;
  вдвое слабее — разности вдвое меньше: TC TS 0,9, TN 0,7; FC ZSF 0,275, ZNF 0,1.
Правило C и исход «головы воздерживаются» — вероятность дойти до исхода при истинной доле p (0; 0,02; 0,05).
Третий сценарий «по пилоту Sonnet» (совет 44): TC TS 1,0, TN 0,95; FC ZSF 0,05, ZNF 0. Значения закреплены до данных.
ЗАРАНЕЕ (до данных) для весов опоры: «повторилось» — проверки по сценарию «вдвое слабее», исходы-границы — доля 5 %;
«не повторилось» (отрицательный вес) — мощность по сценарию «по пилоту Sonnet» (совет 44, п. в)."""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '2026-11-12_PLATON-01'))
import power_platon as PP          # noqa: E402
import platon_analyze as A         # noqa: E402

N = 40
SCEN = {'наблюдённый в PLATON-01': {'FC_ZS': 0.0, 'FC_ZN': 0.0, 'TC_TS': 1.0, 'TC_TN': 0.6, 'FC_ZSF': 0.45, 'FC_ZNF': 0.1},
        'вдвое слабее': {'FC_ZS': 0.0, 'FC_ZN': 0.0, 'TC_TS': 0.9, 'TC_TN': 0.7, 'FC_ZSF': 0.275, 'FC_ZNF': 0.1},
        # совет 44, п. б: по пилоту Sonnet (TS 2/2, TN 2/2, ZSF 0/2, ZNF 0/2); значения закреплены до данных
        'по пилоту Sonnet': {'FC_ZS': 0.0, 'FC_ZN': 0.0, 'TC_TS': 1.0, 'TC_TN': 0.95, 'FC_ZSF': 0.05, 'FC_ZNF': 0.0}}
TC_CONF_TSF = 0.975    # доля верного согласия с порогом в TSF: PLATON-01 (39/40); у Sonnet в пилоте 2/2


def reach(p, n=N):
    kmax = max(k for k in range(n + 1) if A.cp_upper_one_sided(k, n) < A.EQUIV_UPPER)
    return kmax, A.binom_cdf(kmax, n, p)


def p_tc_ok(rate, n=N):
    """P(доля верных согласий с порогом в TSF ≥ 0,3) при истинной доле rate: P(X ≥ 12 из 40)."""
    k = math.ceil(A.POS_CONTROL * n)
    return A.binom_sf(k, n, rate)


def main():
    out = {'n': N, 'family': {}, 'bounds': {},
           'weights_rule': 'повторилось: проверки — «вдвое слабее», исходы-границы — доля 5 %; не повторилось: мощность «по пилоту Sonnet»'}
    for name, r in SCEN.items():
        out['family'][name] = PP.power_family(N, r)
    tc = p_tc_ok(TC_CONF_TSF)
    for p in (0.0, 0.02, 0.05):
        kmax, one = reach(p)
        # свободный режим: обе ячейки Z — нижняя граница Фреше max(0, 2·one − 1), без предположения независимости
        # (совет 44, п. б); правило C: ячейка ZSF × P(TC с порогом в TSF ≥ 0,3)
        out['bounds'][str(p)] = {'max_allowed': kmax, 'one_cell': one, 'free_both_cells_frechet_lower': max(0.0, 2 * one - 1),
                                 'rule_C': one * tc, 'P_TC_conf_TSF_ok': tc}
    # ложный уровень исходов-границ: вероятность исхода при истинной доле 0,15 (≤ 0,05 по построению Клоппера — Пирсона)
    kmax, at015 = reach(0.15)
    out['bounds_false_level_at_0.15_one_cell'] = at015
    out['mc'] = {'reps': PP.REPS, 'seed_family': 606}
    json.dump(out, open(os.path.join(HERE, 'power_r.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
