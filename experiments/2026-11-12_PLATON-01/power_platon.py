#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-01: мощность и ложный уровень до прогона (точно для P1, Монте-Карло для P2 и Холма).

P1: точный односторонний биномиальный тест «ложное согласие в ZS > 0,05»; P2: точный односторонний тест Макнемара
«ZS > ZN» (парно по экземпляру); P3 (после пилота a): Макнемар «верное согласие TS > TN». Холм на трёх проверках
при общем α = 0,05. Сетка P1/P2 — для Холма на трёх в двух крайних случаях: P3 не отвергнута (худший для P1/P2:
первый шаг α/3) и P3 отвергнута первой (тогда P1/P2 идут как Холм на двух).
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
# Сценарии для семьи из шести проверок; доли свободного режима — по пилотам a и b (FC 0 из 20 в каждой ячейке Z;
# TC TS 19/20, TN 10/20). Доли режима F вписываются после пилота F (до регистрации) — см. PREREG §9.
FAMILY_SCENARIOS = {
    'пилоты; F как задумано (ZSF 0,5, ZNF 0,05)': {'FC_ZS': 0.0, 'FC_ZN': 0.0, 'TC_TS': 0.95, 'TC_TN': 0.5, 'FC_ZSF': 0.5, 'FC_ZNF': 0.05},
    'вдвое слабее (ZSF 0,25, TN 0,7)': {'FC_ZS': 0.0, 'FC_ZN': 0.0, 'TC_TS': 0.9, 'TC_TN': 0.7, 'FC_ZSF': 0.25, 'FC_ZNF': 0.05},
}
PS = [0.15, 0.25, 0.4, 0.6]
PN = [0.0, 0.05, 0.1]
REPS = 20000


def crit_p1(n, alpha):
    """Наименьшее k, при котором P(X ≥ k | 0,05) ≤ alpha."""
    for k in range(n + 1):
        if A.binom_sf(k, n, A.P0) <= alpha:
            return k
    return n + 1


def power_mc(n, ps, pn, reps=REPS, seed=20261112, p3=1.0):
    """Мощность P1, P2 и обеих вместе по Холму на трёх проверках; p3 — фиксированное p проверки P3
    (0 — P3 отвергнута первой, тогда P1/P2 идут как Холм на двух; 1 — P3 не отвергнута, худший случай)."""
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
            h = A.holm({'P1': p1, 'P2': p2, 'P3': p3})
            cache[key] = (h['P1'], h['P2'])
        a1, a2 = cache[key]
        rej1 += a1; rej2 += a2; both += a1 and a2
    return rej1 / reps, rej2 / reps, both / reps


def power_p3(n, pts, ptn, reps=REPS, seed=33, p1_rejects=False):
    """Мощность P3 (TC(TS) > TC(TN), Макнемар) по Холму на трёх проверках. Худший случай для порога — P1 и P2 не
    отвергнуты (ожидание пилота): тогда P3 проходит только при p3 ≤ α/3 на первом шаге Холма."""
    g = np.random.default_rng(seed)
    s = g.random((reps, n)) < pts
    z = g.random((reps, n)) < ptn
    rej = 0
    for r in range(reps):
        b = int((s[r] & ~z[r]).sum()); c = int((~s[r] & z[r]).sum())
        p3 = A.binom_sf(b, b + c, 0.5) if b + c else 1.0
        h = A.holm({'P1': 0.0 if p1_rejects else 1.0, 'P2': 1.0, 'P3': p3})
        rej += h['P3']
    return rej / reps


def power_family(n, rates, reps=REPS, seed=606):
    """Мощность каждой из шести проверок при одной семье Холма (α = 0,05), оценка Монте-Карло.
    rates: доли событий по ячейкам — FC_ZS, FC_ZN, TC_TS, TC_TN (свободный), FC_ZSF, FC_ZNF (режим F).
    Ячейки моделируются независимо (консервативно для Макнемара при положительной связи)."""
    g = np.random.default_rng(seed)
    sim = {k: g.random((reps, n)) < v for k, v in rates.items()}
    cnt = {k: 0 for k in ('P1', 'P2', 'P3', 'P1F', 'P2F', 'P4')}
    cache = {}

    def mc(a, b):
        bb = int((a & ~b).sum()); cc = int((~a & b).sum())
        return A.binom_sf(bb, bb + cc, 0.5) if bb + cc else 1.0
    for r in range(reps):
        zs, zn, ts, tn, zsf, znf = (sim[k][r] for k in ('FC_ZS', 'FC_ZN', 'TC_TS', 'TC_TN', 'FC_ZSF', 'FC_ZNF'))
        pv = {'P1': A.binom_sf(int(zs.sum()), n, A.P0), 'P2': mc(zs, zn), 'P3': mc(ts, tn),
              'P1F': A.binom_sf(int(zsf.sum()), n, A.P0), 'P2F': mc(zsf, znf), 'P4': mc(zsf, zs)}
        key = tuple(round(v, 12) for v in pv.values())
        if key not in cache:
            cache[key] = A.holm(pv)
        for k, v in cache[key].items():
            cnt[k] += v
    return {k: v / reps for k, v in cnt.items()}


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
            # P3 под нулём: TC(TS) и TC(TN) одинаково распределены (те же s, z в роли TS, TN)
            p3 = A.binom_sf(c, b + c, 0.5) if b + c else 1.0
            h = A.holm({'P1': p1, 'P2': p2, 'P3': p3})
            any_rej += h['P1'] or h['P2'] or h['P3']
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
        # вероятность дойти до третьего исхода, если истинная доля ложного согласия p в обеих ячейках Z
        # (ячейки независимы): P(X ≤ kmax | n, p)²
        reach = {f'P_reach_if_p_{p}_both': (A.binom_cdf(kmax, n, p) ** 2 if kmax >= 0 else 0.0) for p in (0.0, 0.02, 0.05)}
        res['third_outcome'][n] = {'max_FC_allowed': kmax, **reach}
        res['false_level'][n] = false_level_mc(n)
        for ps in PS:
            for pn in PN:
                p1, p2, both = power_mc(n, ps, pn, p3=1.0)
                q1, q2, qb = power_mc(n, ps, pn, p3=0.0)
                res['grid'].append({'n': n, 'p_ZS': ps, 'p_ZN': pn, 'power_P1_p3not': p1, 'power_P2_p3not': p2,
                                    'power_both_p3not': both, 'power_P1_p3rej': q1, 'power_P2_p3rej': q2, 'power_both_p3rej': qb})
    res['P3'] = []
    for n in NS:
        for pts, ptn in ((0.9, 0.5), (0.8, 0.6), (0.85, 0.65), (0.7, 0.5)):
            res['P3'].append({'n': n, 'TC_TS': pts, 'TC_TN': ptn, 'power_P3_holm3': power_p3(n, pts, ptn)})
    # семья из шести проверок при долях пилотов (свободный режим — пилоты a и b; режим F — пилот F, см. --rates)
    res['family'] = []
    for name, rates in FAMILY_SCENARIOS.items():
        res['family'].append({'scenario': name, 'n': 40, 'rates': rates, 'power': power_family(40, rates)})
    print('критическое k для P1 (α 0,025 / 0,05):', res['crit_P1_alpha_0.025'], res['crit_P1_alpha_0.05'])
    for f in res['family']:
        print('семья, n 40,', f['scenario'], f['rates'], '→', {k: round(v, 3) for k, v in f['power'].items()})
    print('P3 (Холм на трёх, P1 и P2 не отвергнуты):', [(r['n'], r['TC_TS'], r['TC_TN'], round(r['power_P3_holm3'], 3)) for r in res['P3']])
    print('третий исход:', res['third_outcome'])
    print('ложный уровень серии (оценка Монте-Карло):', res['false_level'])
    print('n   p_ZS  p_ZN  | P3 не отвергнута: P1  P2  оба | P3 отвергнута: P1  P2  оба')
    for r in res['grid']:
        print(f"{r['n']:<3} {r['p_ZS']:<5} {r['p_ZN']:<5} | {r['power_P1_p3not']:.3f} {r['power_P2_p3not']:.3f} {r['power_both_p3not']:.3f}"
              f" | {r['power_P1_p3rej']:.3f} {r['power_P2_p3rej']:.3f} {r['power_both_p3rej']:.3f}")
    with open(a.out, 'w', encoding='utf-8') as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
