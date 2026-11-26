#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04: верхняя граница |недостача М − недостача Т| / ε по задачам теста (PREREG §4 «Нормировка»; совет 78, п. 6).
Граница — (|S| + K + число кандидатов операторов каталога вне V) / |V|:
  |S| = 2^(число разрядов с переносом) — опора части переноса (distill02.position_features);
  K — размер таблицы нуля-Т (= числу операторов каталога);
  V — справочное множество distill02.ref_size.
Это граница при любых весах: доли остатка у М (π_U/Z) и у Т (q_rest/tot) не больше 1 (формулы — test_prog_m.deficit_formula,
сверены перебором). Считается только из входов задач (a, b) сред test6 и test6L, без ответов голов. Каталог — из вывода пилота 2.
  python3 norm_bound_d4.py [ВЫХОД.json]"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import distill04_extract as X4  # noqa: E402
import prog_m as PM  # noqa: E402

D2 = PM.D2
CATALOG = json.load(open(os.path.join(ROOT, 'gha_out/distill04_pilot2/pilot.json'), encoding='utf-8'))['catalog']
K = len(CATALOG)


def bound(a, b):
    s = a + b
    n = len(str(s))
    lo, hi = 10 ** max(n - 3, 0), 10 ** (n + 1)
    n_s = 2 ** len(D2.position_features(a, b, 0))
    cand = PM.candidates(a, b)
    out = set().union(*[cand[op] for op in CATALOG])
    n_out = sum(not (lo <= y < hi) for y in out)
    return (n_s + K + n_out) / D2.ref_size(s), n_s, n_out


def main(a):
    res = {}
    for phase in ('test6', 'test6L'):
        for env in X4.envs_d4(phase):
            vals = [bound(p['a'], p['b']) for p in env['problems']]
            res[env['name']] = dict(max_bound=max(v[0] for v in vals), max_S=max(v[1] for v in vals), max_out_V=max(v[2] for v in vals),
                                    n=len(vals))
            print(env['name'], '| наибольшая граница / ε', f"{res[env['name']]['max_bound']:.3e}", '| наибольшее |S|', res[env['name']]['max_S'],
                  '| кандидатов вне V', res[env['name']]['max_out_V'], flush=True)
    mx = max(r['max_bound'] for r in res.values())
    print(f'наибольшая по всем задачам test6 и test6L граница |недостача М − недостача Т| / ε: {mx:.3e} (каталог {K} операторов, K = {K})')
    if a:
        json.dump(dict(catalog=CATALOG, K=K, envs=res, max_bound=mx), open(a[0], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
