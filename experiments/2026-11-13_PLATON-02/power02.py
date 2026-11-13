#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-02: мощность до прогона → power02.json. P1, P2 — точный биномиальный «доля FC_X > 0,05»; P3 — Макнемар
«TC_Y(MN) > TC_Y(M)» (ячейки независимы); Холм на трёх. Оценка МК: 20 000 повторов, зерно 202.
Сценарии: «гипотеза» — FC_X 0,25 в обоих режимах, TC_Y MN 0,8 против M 0,6; «вдвое слабее» — FC_X 0,125, TC_Y 0,8 против 0,7;
«по пилоту» — FC_X 0, TC_Y 0,75 и 0,75. Исход «редко» (верхняя граница FC_X < 0,15) — достижимость при доле 2 % и 5 %.
Для весов заранее: подтверждение — «вдвое слабее»; исход «редко» — доля 5 %."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', '2026-11-12_PLATON-01'))
import platon_analyze as A    # noqa: E402
N, REPS = 40, 20000
SC = {'гипотеза': (0.25, 0.25, 0.8, 0.6), 'вдвое слабее': (0.125, 0.125, 0.8, 0.7), 'по пилоту': (0.0, 0.0, 0.75, 0.75)}


def power(fx_f, fx_free, tmn, tm):
    g = np.random.default_rng(202); cnt = {'P1': 0, 'P2': 0, 'P3': 0}; cache = {}
    for _ in range(REPS):
        k1 = int((g.random(N) < fx_f).sum()); k2 = int((g.random(N) < fx_free).sum())
        a = g.random(N) < tmn; b = g.random(N) < tm
        bb = int((a & ~b).sum()); cc = int((~a & b).sum())
        key = (k1, k2, bb, cc)
        if key not in cache:
            cache[key] = A.holm({'P1': A.binom_sf(k1, N, A.P0), 'P2': A.binom_sf(k2, N, A.P0),
                                 'P3': A.binom_sf(bb, bb + cc, 0.5) if bb + cc else 1.0})
        for k, v in cache[key].items():
            cnt[k] += v
    return {k: v / REPS for k, v in cnt.items()}


kmax = max(k for k in range(N + 1) if A.cp_upper_one_sided(k, N) < A.EQUIV_UPPER)
out = {'n': N, 'reps': REPS, 'seed': 202, 'family': {k: power(*v) for k, v in SC.items()},
       'rare_reach': {str(p): A.binom_cdf(kmax, N, p) for p in (0.0, 0.02, 0.05)}, 'rare_max_allowed': kmax,
       'weights_rule': 'подтверждение — «вдвое слабее»; исход «редко» — доля 5 %'}
json.dump(out, open(os.path.join(HERE, 'power02.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
