#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-02: мощность до прогона → power02.json (слой A, n = 42). P1A, P2A — точный биномиальный «доля FC_X > 0,05», Холм на двух
(совет 46); P3 — описательно: односторонний Макнемар «TC_Y(MN) > TC_Y(M)» без поправки (ячейки независимы). МК: 20 000 повторов, зерно 202.
Сценарии: «гипотеза» — FC_X 0,25 в обоих режимах, TC_Y MN 0,8 против M 0,6; «вдвое слабее» — FC_X 0,125, TC_Y 0,8 против 0,7;
«по пилоту» — FC_X 0, TC_Y 0,75 и 0,75. Исход «редко» (верхняя граница FC_X < 0,15) — достижимость при доле 2 % и 5 %.
Для весов заранее: подтверждение — «вдвое слабее» (P1A); опровержение узко («редко» в обоих режимах) — доля 5 %, граница Фреше."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', '2026-11-12_PLATON-01'))
import platon_analyze as A    # noqa: E402
N, REPS = 42, 20000            # слой A: 7 законов × 6 экземпляров (совет 46: главный вердикт — по слою A)
SC = {'гипотеза': (0.25, 0.25, 0.8, 0.6), 'вдвое слабее': (0.125, 0.125, 0.8, 0.7), 'по пилоту': (0.0, 0.0, 0.75, 0.75)}


def power(fx_f, fx_free, tmn, tm):
    """Семья Холма — P1A и P2A (совет 46); P3 — описательно, её мощность одна (без Холма)."""
    g = np.random.default_rng(202); cnt = {'P1A': 0, 'P2A': 0, 'P3_descr': 0}; cache = {}
    for _ in range(REPS):
        k1 = int((g.random(N) < fx_f).sum()); k2 = int((g.random(N) < fx_free).sum())
        a = g.random(N) < tmn; b = g.random(N) < tm
        bb = int((a & ~b).sum()); cc = int((~a & b).sum())
        key = (k1, k2)
        if key not in cache:
            cache[key] = A.holm({'P1A': A.binom_sf(k1, N, A.P0), 'P2A': A.binom_sf(k2, N, A.P0)})
        for k, v in cache[key].items():
            cnt[k] += v
        cnt['P3_descr'] += (A.binom_sf(bb, bb + cc, 0.5) if bb + cc else 1.0) <= 0.05
    return {k: v / REPS for k, v in cnt.items()}


kmax = max(k for k in range(N + 1) if A.cp_upper_one_sided(k, N) < A.EQUIV_UPPER)
one = {str(p): A.binom_cdf(kmax, N, p) for p in (0.0, 0.02, 0.05)}
out = {'n_layer_A': N, 'reps': REPS, 'seed': 202, 'family': {k: power(*v) for k, v in SC.items()},
       'rare_reach_one_cell': one, 'rare_reach_both_frechet': {p: max(0.0, 2 * v - 1) for p, v in one.items()},
       'rare_max_allowed': kmax,
       'weights_rule': 'подтверждение — «вдвое слабее» (P1A); опровержение узко («редко» в обоих режимах) — доля 5 %, граница Фреше'}
half, fre5 = out['family']['вдвое слабее'], out['rare_reach_both_frechet']['0.05']
out['weights_bits'] = {'confirm_P1A': float(np.log2(half['P1A'] / 0.05)), 'confirm_P2A': float(np.log2(half['P2A'] / 0.05)),
                       'refute_narrow_A': float(np.log2(fre5 / 0.05)) if fre5 > 0 else None}
out['reject_P1A_min_k'] = min(k for k in range(N + 1) if A.binom_sf(k, N, A.P0) <= A.ALPHA / 2)
out['cp_upper'] = {f'{k}/{N}': A.cp_upper_one_sided(k, N) for k in (0, 1, 2, 3)}
out['cp_upper_layer_B_0_of_12'] = A.cp_upper_one_sided(0, 12)
json.dump(out, open(os.path.join(HERE, 'power02.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
