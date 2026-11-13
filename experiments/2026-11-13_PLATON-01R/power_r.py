#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-01R: мощность до прогона (решение совета 43) → power_r.json.
Функции — из ../2026-11-12_PLATON-01/power_platon.py и platon_analyze.py (код не меняется).
Сценарии (доли PLATON-01, run/results_platon01.json):
  наблюдённый — FC ZS 0, ZN 0; TC TS 1,0, TN 0,6; FC ZSF 0,45, ZNF 0,1;
  вдвое слабее — разности вдвое меньше: TC TS 0,9, TN 0,7; FC ZSF 0,275, ZNF 0,1.
Правило C и исход «головы воздерживаются» — вероятность дойти до исхода при истинной доле p (0; 0,02; 0,05).
ЗАРАНЕЕ (до данных) для весов опоры берётся: проверки — сценарий «вдвое слабее»; исходы-границы — p = 0,05."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '2026-11-12_PLATON-01'))
import power_platon as PP          # noqa: E402
import platon_analyze as A         # noqa: E402

N = 40
SCEN = {'наблюдённый в PLATON-01': {'FC_ZS': 0.0, 'FC_ZN': 0.0, 'TC_TS': 1.0, 'TC_TN': 0.6, 'FC_ZSF': 0.45, 'FC_ZNF': 0.1},
        'вдвое слабее': {'FC_ZS': 0.0, 'FC_ZN': 0.0, 'TC_TS': 0.9, 'TC_TN': 0.7, 'FC_ZSF': 0.275, 'FC_ZNF': 0.1}}


def reach(p, n=N):
    kmax = max(k for k in range(n + 1) if A.cp_upper_one_sided(k, n) < A.EQUIV_UPPER)
    return kmax, A.binom_cdf(kmax, n, p)


def main():
    out = {'n': N, 'family': {}, 'bounds': {}, 'weights_rule': 'проверки — «вдвое слабее»; исходы-границы — p = 0,05'}
    for name, r in SCEN.items():
        out['family'][name] = PP.power_family(N, r)
    for p in (0.0, 0.02, 0.05):
        kmax, one = reach(p)
        # свободный режим: обе ячейки Z; правило C: одна ячейка ZSF (и TC при пороге в TSF ≥ 0,3 — при доле 0,975 почти наверняка)
        out['bounds'][str(p)] = {'max_allowed': kmax, 'free_both_cells': one ** 2, 'rule_C_one_cell': one}
    json.dump(out, open(os.path.join(HERE, 'power_r.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
