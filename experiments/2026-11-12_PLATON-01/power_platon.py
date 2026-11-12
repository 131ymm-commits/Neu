#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-01: мощность и ложный уровень до прогона (точно для P1, Монте-Карло для P2 и Холма).

P1: точный односторонний биномиальный тест «ложное согласие в ZS > 0,05»; P2: точный односторонний тест Макнемара
«ZS > ZN» (парно по экземпляру). Холм на двух проверках при общем α = 0,05.
Мощность считается по Холму: P1 и P2 отвергаются вместе (оценка Монте-Карло, 20 000 повторов, зерно фиксировано).
Совместная модель: ячейки ZS и ZN независимы при заданных вероятностях (консервативно для Макнемара, если события
положительно связаны, — мощность выше).
Третий исход: верхняя односторонняя 95 % граница Клоппера — Пирсона < 0,15 в ZS и в ZN.
Запуск: python3 power_platon.py [--out power_platon.json]
"""
import argparse
import json

import numpy as np

import platon_analyze as A

NS = [20, 30, 40]
PS = [0.15, 0.25, 0.4, 0.6]
PN = [0.0, 0.05, 0.1]
REPS = 20000


def crit_p1(n, alpha):
    """Наименьшее k, при котором P(X ≥ k | 0,05) ≤ alpha."""
    for k in range(n + 1):
        if A.binom_sf(k, n, A.P0) <= alpha:
            return k
    return n + 1


def power_mc(n, ps, pn, reps=REPS, seed=20261112):
    g = np.random.default_rng(seed)
    s = g.random((reps, n)) < ps
    z = g.random((reps, n)) < pn
    rej1 = rej2 = both = 0
    cache = {}
    for r in range(reps):
        k = int(s[r].sum())
        b = int((s[r] & ~z[r]).sum()); c = int((~s[r] & z[r]).sum())
        key = (k, b, c)
        if key not in cache:
            p1 = A.binom_sf(k, n, A.P0)
            p2 = A.binom_sf(b, b + c, 0.5) if b + c else 1.0
            h = A.holm({'P1': p1, 'P2': p2})
            cache[key] = (h['P1'], h['P2'])
        a1, a2 = cache[key]
        rej1 += a1; rej2 += a2; both += a1 and a2
    return rej1 / reps, rej2 / reps, both / reps


def false_level_mc(n, reps=REPS, seed=7):
    """Ложный уровень серии: P1 при p = 0,05 (граница нуля) и P2 при ps = pn (худший случай — pn = ps = 0,05…0,3)."""
    out = {}
    for p in (0.05, 0.15, 0.3):
        g = np.random.default_rng(seed)
        s = g.random((reps, n)) < max(p, A.P0) if p == 0.05 else g.random((reps, n)) < p
        z = g.random((reps, n)) < p
        any_rej = 0
        for r in range(reps):
            k = int(s[r].sum()) if p == 0.05 else 0      # при p > 0,05 нуль P1 ложен — считаем только P2
            b = int((s[r] & ~z[r]).sum()); c = int((~s[r] & z[r]).sum())
            p1 = A.binom_sf(k, n, A.P0) if p == 0.05 else 1.0
            p2 = A.binom_sf(b, b + c, 0.5) if b + c else 1.0
            h = A.holm({'P1': p1, 'P2': p2})
            any_rej += h['P1'] or h['P2']
        out[str(p)] = any_rej / reps
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='power_platon.json')
    a = ap.parse_args()
    res = {'reps': REPS, 'grid': [], 'crit_P1_alpha_0.025': {}, 'crit_P1_alpha_0.05': {}, 'third_outcome': {},
           'false_level': {}}
    for n in NS:
        res['crit_P1_alpha_0.025'][n] = crit_p1(n, 0.025)
        res['crit_P1_alpha_0.05'][n] = crit_p1(n, 0.05)
        # третий исход: при скольких ложных согласиях верхняя граница ещё < 0,15
        kmax = max([k for k in range(n + 1) if A.cp_upper_one_sided(k, n) < A.EQUIV_UPPER], default=-1)
        res['third_outcome'][n] = {'max_FC_allowed': kmax,
                                   'P_reach_if_p_0': 1.0 if kmax >= 0 else 0.0,
                                   'P_reach_if_p_0.02_both': float(sum(A.binom_sf(0, n, 0.02) - A.binom_sf(kmax + 1, n, 0.02)
                                                                       for _ in [0])) ** 2 if kmax >= 0 else 0.0}
        res['false_level'][n] = false_level_mc(n)
        for ps in PS:
            for pn in PN:
                p1, p2, both = power_mc(n, ps, pn)
                res['grid'].append({'n': n, 'p_ZS': ps, 'p_ZN': pn, 'power_P1': p1, 'power_P2': p2, 'power_both': both})
    print('критическое k для P1 (α 0,025 / 0,05):', res['crit_P1_alpha_0.025'], res['crit_P1_alpha_0.05'])
    print('третий исход:', res['third_outcome'])
    print('ложный уровень серии (оценка Монте-Карло):', res['false_level'])
    print('n   p_ZS  p_ZN  P1     P2     оба')
    for r in res['grid']:
        print(f"{r['n']:<3} {r['p_ZS']:<5} {r['p_ZN']:<5} {r['power_P1']:.3f}  {r['power_P2']:.3f}  {r['power_both']:.3f}")
    with open(a.out, 'w', encoding='utf-8') as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
