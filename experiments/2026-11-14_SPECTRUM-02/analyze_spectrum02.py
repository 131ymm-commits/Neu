#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-02: анализ. python3 analyze_spectrum02.py RESULTS.json OUT.json
Меры группы — analyze_spectrum01.group_measures (t_align: порог по половине A — середина подъёма средней CKA,
пересечение по половине B с линейной интерполяцией; только при d_cka ≥ 0,1). λ_max — наибольшая из λ кластеров
(среднее по 4 сетям блока).
Правила (вес несут P1, P2, P4; P3 — та же группа опор, что P2; пороги — PREREG §5). N = 30 блоков, NEED = 23
(ложный уровень знака P(X ≥ 23 | 30, ½) = 0,0026); при другом числе блоков (пилот, заглушки) NEED = ⌈23/30·n⌉.
  P1 (повтор C-079): t_align(A0) > t_align(A1) не меньше чем в NEED блоках из N; опровержение — t(A0) < t(A1) в NEED.
  P2 (кратность при равном λ_max): t_align(AB1) < t_align(A1) в NEED; опровержение — t(AB1) > t(A1) в NEED.
  P3 (показатель): α_b = −наклон МНК ln t_align на ln λ_max по 4 уровням; развёртка A (A0, A⅓, A⅔, A1) и AB (A0, AB⅓,
      AB⅔, AB1); α_AB > α_A в NEED; опровержение — α_AB < α_A в NEED.
  P4 (форма закона при постоянной кратности): пул-показатель α_AB = −наклон ln(медиана по блокам t_align) на
      ln(медиана λ_max) по 4 условиям AB; ДИ 99 % — бутстреп по блокам (10 000, зерно 505). Подтверждено: ДИ строго
      внутри (1/3; 2/3); опровергнуто: ДИ целиком ≤ 1/3 или ≥ 2/3; иначе «не решено».
Проверки метода (вес 0; провал любой → вердикт «не определено»): d_cka ≥ 0,1 во всех группах (t_align определено);
  |λ_max(AB1)/λ_max(A1) − 1| ≤ 0,03 во всех блоках; λ_max растёт по развёрткам A и AB во всех блоках;
  симметрия |медиана(t(B1)/t(A1)) − 1| ≤ SYM_TOL.
Описательно: медианы α_A, α_AB с ДИ; отношение t(A1)/t(AB1) с ДИ; t½ объектов; показатель поведения «я»."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '2026-11-13_SPECTRUM-01'))
import analyze_spectrum01 as A1  # noqa: E402

N_TEST, K_TEST = 30, 23  # знаковое правило: не меньше 23 из 30
BAND = (1 / 3, 2 / 3)
CI_P4 = 99.0
SYM_TOL = 0.05
LAM_TOL = 0.03
SWEEP_A = ['A0', 'A13', 'A23', 'A1']
SWEEP_AB = ['A0', 'AB13', 'AB23', 'AB1']


def alpha(ts, lams):
    if any(t is None or t <= 0 for t in ts):
        return None
    return float(-np.polyfit(np.log(lams), np.log(ts), 1)[0])


def sign_rule(xs, ys, need):
    """k: x > y; k_rev: x < y (ничьи не засчитываются ни туда, ни сюда)."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    return len(pairs), sum(x > y for x, y in pairs), sum(x < y for x, y in pairs)


def verdict(n_def, k, k_rev, need):
    if n_def >= need and k >= need:
        return 'подтверждено'
    if k_rev >= need:
        return 'опровергнуто'
    return 'не решено'


def main(src, dst):
    d = json.load(open(src, encoding='utf-8'))
    M = []
    for g in d['groups']:
        m = A1.group_measures(g)
        m.update(cond=g['cond'], qa=g['qa'], qb=g['qb'], lam_max=float(max(m['lam'].values())))
        M.append(m)
    idx = {(m['block'], m['cond']): m for m in M}
    blocks = sorted({m['block'] for m in M})
    n = len(blocks)
    need = K_TEST if n == N_TEST else int(np.ceil(K_TEST / N_TEST * n))
    t = lambda c: [idx[(b, c)]['t_align'] for b in blocks]          # noqa: E731
    lm = lambda c: [idx[(b, c)]['lam_max'] for b in blocks]         # noqa: E731
    res = dict(blocks=n, need=need, measures=M)
    nd, k, kr = sign_rule(t('A0'), t('A1'), need)
    r1 = [x / y for x, y in zip(t('A0'), t('A1')) if x and y]
    res['P1'] = dict(n_defined=nd, k=k, k_rev=kr, verdict=verdict(nd, k, kr, need), ratio_A0_A1=r1,
                     median_ratio=float(np.median(r1)) if r1 else None, ci95=A1.boot_ci(r1) if r1 else None)
    nd, k, kr = sign_rule(t('A1'), t('AB1'), need)               # x = t(A1) > y = t(AB1) — в пользу гипотезы
    r2 = [x / y for x, y in zip(t('A1'), t('AB1')) if x and y]
    res['P2'] = dict(n_defined=nd, k=k, k_rev=kr, verdict=verdict(nd, k, kr, need), ratio_A1_AB1=r2,
                     median_ratio=float(np.median(r2)) if r2 else None, ci95=A1.boot_ci(r2) if r2 else None)
    aA = [alpha([idx[(b, c)]['t_align'] for c in SWEEP_A], [idx[(b, c)]['lam_max'] for c in SWEEP_A]) for b in blocks]
    aAB = [alpha([idx[(b, c)]['t_align'] for c in SWEEP_AB], [idx[(b, c)]['lam_max'] for c in SWEEP_AB]) for b in blocks]
    nd, k, kr = sign_rule(aAB, aA, need)
    diff = [x - y for x, y in zip(aAB, aA) if x is not None and y is not None]
    res['P3'] = dict(n_defined=nd, k=k, k_rev=kr, verdict=verdict(nd, k, kr, need), alpha_A=aA, alpha_AB=aAB,
                     median_alpha_A=float(np.median([a for a in aA if a is not None])) if any(a is not None for a in aA) else None,
                     ci95_alpha_A=A1.boot_ci([a for a in aA if a is not None]) if any(a is not None for a in aA) else None,
                     median_alpha_AB=float(np.median([a for a in aAB if a is not None])) if any(a is not None for a in aAB) else None,
                     ci95_alpha_AB=A1.boot_ci([a for a in aAB if a is not None]) if any(a is not None for a in aAB) else None,
                     diff=diff, median_diff=float(np.median(diff)) if diff else None, ci95_diff=A1.boot_ci(diff) if diff else None)
    # P4: пул-показатель по развёртке AB (и описательно — по A)
    def pooled(sweep, bidx):
        T = np.array([[idx[(blocks[i], c)]['t_align'] for c in sweep] for i in bidx], float)
        L = np.array([[idx[(blocks[i], c)]['lam_max'] for c in sweep] for i in bidx], float)
        return float(-np.polyfit(np.log(np.median(L, 0)), np.log(np.median(T, 0)), 1)[0])
    p4 = {}
    defined_all = all(idx[(b, c)]['t_align'] is not None for b in blocks for c in SWEEP_AB + SWEEP_A)
    if defined_all:
        g4 = np.random.default_rng(505)
        for name, sw in (('AB', SWEEP_AB), ('A', SWEEP_A)):
            est = pooled(sw, range(n))
            bs = [pooled(sw, g4.integers(0, n, n)) for _ in range(10000)]
            lo, hi = np.percentile(bs, [(100 - CI_P4) / 2, 100 - (100 - CI_P4) / 2])
            p4[name] = dict(alpha=est, ci99=[float(lo), float(hi)])
        lo, hi = p4['AB']['ci99']
        v4 = 'подтверждено' if BAND[0] < lo and hi < BAND[1] else ('опровергнуто' if hi <= BAND[0] or lo >= BAND[1] else 'не решено')
    else:
        v4 = 'не решено'
    res['P4'] = dict(verdict=v4, band=list(BAND), ci_level=CI_P4, defined_all=defined_all, **p4)
    # проверки метода
    dmin = float(min(m['d_cka'] for m in M))
    sym = [x / y for x, y in zip(t('B1'), t('A1')) if x and y]
    lam_ratio = [x / y for x, y in zip(lm('AB1'), lm('A1'))]
    res['method'] = dict(
        d_cka_min=dmin, d_cka_ok=dmin >= A1.THR_LAZY_D,
        sym_ratio_B1_A1=sym, sym_median=float(np.median(sym)) if sym else None, sym_ci95=A1.boot_ci(sym) if sym else None,
        sym_ok=bool(sym and abs(np.median(sym) - 1) <= SYM_TOL),
        lam_ratio_AB1_A1=lam_ratio, lam_ok=all(abs(x - 1) <= LAM_TOL for x in lam_ratio),
        lam_monotone=all(all(np.diff([idx[(b, c)]['lam_max'] for c in sw]) > 0) for b in blocks for sw in (SWEEP_A, SWEEP_AB)))
    mm = res['method']
    method_ok = mm['d_cka_ok'] and mm['lam_ok'] and mm['lam_monotone'] and mm['sym_ok']
    # описательно: t½ «я» и показатель поведения по развёртке A
    beh = [alpha([idx[(b, c)]['t_half_obj'][0] for c in SWEEP_A], [idx[(b, c)]['lam']['S'] for c in SWEEP_A]) for b in blocks]
    res['descr'] = dict(alpha_behav_self_A=beh, median_alpha_behav_self_A=float(np.median([x for x in beh if x is not None])) if any(x is not None for x in beh) else None,
                        t_align={c: t(c) for c in d['conds']}, lam_max={c: lm(c) for c in d['conds']},
                        t_half_self={c: [idx[(b, c)]['t_half_obj'][0] for b in blocks] for c in d['conds']},
                        perm_vs_init_min_gap=float(min(m['cka0'] - m['perm_max'] for m in M)))
    res['verdicts'] = {p: res[p]['verdict'] for p in ('P1', 'P2', 'P3', 'P4')}
    if not method_ok:
        res['verdict'] = 'не определено: проверка метода не прошла'
    else:
        res['verdict'] = '; '.join(f'{p}: {res[p]["verdict"]}' for p in ('P1', 'P2', 'P3', 'P4'))
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for p in ('P1', 'P2', 'P3'):
        r = res[p]
        extra = (f"медиана отношения {r.get('median_ratio')} ДИ {r.get('ci95')}" if p != 'P3' else
                 f"α_A {r['median_alpha_A']} ДИ {r['ci95_alpha_A']} | α_AB {r['median_alpha_AB']} ДИ {r['ci95_alpha_AB']} | разность {r['median_diff']} ДИ {r['ci95_diff']}")
        print(f"{p}: {r['verdict']}  определено {r['n_defined']}/{n}, за {r['k']}, против {r['k_rev']} | {extra}")
    r4 = res['P4']
    print(f"P4: {r4['verdict']}  α_AB {r4.get('AB')} | α_A (описательно) {r4.get('A')}")
    print(f"метод: d_cka min {mm['d_cka_min']:.3f} ({mm['d_cka_ok']}); симметрия B1/A1 {mm['sym_median']} ({mm['sym_ok']}); "
          f"λ_max AB1/A1 ок {mm['lam_ok']}; λ_max растёт {mm['lam_monotone']}")
    print('вердикт:', res['verdict'])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
