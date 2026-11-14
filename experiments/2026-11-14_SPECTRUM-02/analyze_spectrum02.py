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
Правило формы (вес 0; совет 50, п. 7): Δ_low = t(A1) − t(A1B13), Δ_high = t(A1B23) − t(AB1); Δ_high > Δ_low в NEED — «за
  кратность»; Δ_low ≥ Δ_high в NEED — «за добавочный сигнал»; иначе «не решено». Энергия добавочного сигнала не уравнена.
Общий порог блока (по A1; совет 50, п. 9): если знак P2 или P3 по нему расходится с решающим вердиктом (ничья — тоже
  расхождение), вердикт — «не определено (зависит от порога)».
Мера фазы в момент t_align (описательно): доля снятого лосса, доля выученной нормы кластеров S и O.
Зёрна теста (база 151000) или флаг --test: только N = 30 блоков, иначе остановка.
Проверки метода (вес 0; провал любой → каждый из P1…P4 и правило формы «не определено»): d_cka ≥ 0,1 во всех группах (t_align определено);
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
TEST_BASE = 151000       # зёрна теста (spectrum02.TEST_BASE): с ними — только N = 30 и K = 23, иначе остановка (совет 50, п. 1)
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


def mean_curves(g):
    st = np.array(g['step'], float)
    return st, np.array(g['ckaA']).mean(1), np.array(g['ckaB']).mean(1)


def at_time(st, y, t):
    """Значение кривой y(шаг) в момент t (линейная интерполяция)."""
    return None if t is None else float(np.interp(t, st, y))


def sign_of(k, k_rev):
    return (k > k_rev) - (k < k_rev)


def main(src, dst, test=False):
    d = json.load(open(src, encoding='utf-8'))
    test = test or any(g.get('base') == TEST_BASE for g in d['groups'])
    M = []
    for g in d['groups']:
        m = A1.group_measures(g)
        m.update(cond=g['cond'], qa=g['qa'], qb=g['qb'], lam_max=float(max(m['lam'].values())))
        M.append(m)
    idx = {(m['block'], m['cond']): m for m in M}
    blocks = sorted({m['block'] for m in M})
    n = len(blocks)
    if test and n != N_TEST:
        sys.exit(f'зёрна теста, а блоков {n} вместо {N_TEST}: порог не пересчитывается (совет 50, п. 1) — остановка')
    need = K_TEST if n == N_TEST else int(np.ceil(K_TEST / N_TEST * n))   # пилот и заглушки — пропорционально
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
    mm['lam_ratio_max_dev'] = float(max(abs(x - 1) for x in lam_ratio))
    method_ok = mm['d_cka_ok'] and mm['lam_ok'] and mm['lam_monotone'] and mm['sym_ok']
    G = {(g['block'], g['cond']): g for g in d['groups']}
    # общий порог блока — середина подъёма половины A у A1 (совет 50, п. 9; описательно, но расхождение знака снимает вердикт)
    tc = {}
    for b in blocks:
        st, A, _ = mean_curves(G[(b, 'A1')])
        thr = A[0] + 0.5 * (A[-1] - A[0])
        for c in d['conds']:
            st, _, B = mean_curves(G[(b, c)])
            tc[(b, c)] = A1.crossing(st, B, thr) if idx[(b, c)]['d_cka'] >= A1.THR_LAZY_D else None
    tcl = lambda c: [tc[(b, c)] for b in blocks]                    # noqa: E731
    nd2, k2c, kr2c = sign_rule(tcl('A1'), tcl('AB1'), need)
    aAc = [alpha([tc[(b, c)] for c in SWEEP_A], [idx[(b, c)]['lam_max'] for c in SWEEP_A]) for b in blocks]
    aABc = [alpha([tc[(b, c)] for c in SWEEP_AB], [idx[(b, c)]['lam_max'] for c in SWEEP_AB]) for b in blocks]
    nd3, k3c, kr3c = sign_rule(aABc, aAc, need)
    res['common_threshold'] = dict(t_align={c: tcl(c) for c in d['conds']}, P2=dict(n_defined=nd2, k=k2c, k_rev=kr2c),
                                   P3=dict(n_defined=nd3, k=k3c, k_rev=kr3c))
    for p, (kc, krc) in (('P2', (k2c, kr2c)), ('P3', (k3c, kr3c))):
        v = res[p]['verdict']
        sc = sign_of(kc, krc)
        if (v == 'подтверждено' and sc <= 0) or (v == 'опровергнуто' and sc >= 0):     # ничья по общему порогу — тоже расхождение
            res[p]['verdict_main_threshold'] = v
            res[p]['verdict'] = 'не определено (зависит от порога)'
    # правило формы — контроль смешения кратности и добавочного сигнала (совет 50, п. 7; вес 0; энергия не уравнена)
    dl = [None if None in (x, y) else x - y for x, y in zip(t('A1'), t('A1B13'))]
    dh = [None if None in (x, y) else x - y for x, y in zip(t('A1B23'), t('AB1'))]
    pr = [(h, l) for h, l in zip(dh, dl) if h is not None and l is not None]
    k_mult, k_sig = sum(h > l for h, l in pr), sum(l >= h for h, l in pr)
    vs = ('за кратность' if len(pr) >= need and k_mult >= need else ('за добавочный сигнал' if k_sig >= need else 'не решено'))
    res['shape'] = dict(delta_low=dl, delta_high=dh, n_defined=len(pr), k_mult=k_mult, k_signal=k_sig, verdict=vs,
                        median_delta_low=float(np.median([l for _, l in pr])) if pr else None,
                        median_delta_high=float(np.median([h for h, _ in pr])) if pr else None,
                        ci95_median_diff=A1.boot_ci([h - l for h, l in pr]) if pr else None,
                        note='вес 0; энергия добавочного сигнала не уравнена')
    nd5, k5, kr5 = sign_rule(t('A1B23'), t('AB1'), need)              # описательно (скептик): t(AB1) < t(A1B23)
    res['descr_skeptic_AB1_vs_A1B23'] = dict(n_defined=nd5, k=k5, k_rev=kr5)
    # мера фазы в момент t_align (совет 50, п. 8; описательно)
    phase = {}
    for c in d['conds']:
        rows = []
        for b in blocks:
            g = G[(b, c)]
            if 'loss_frac' not in g:
                continue
            st = np.array(g['step'], float)
            ta = idx[(b, c)]['t_align']
            rows.append([at_time(st, np.array(g[key]).mean(1), ta) for key in ('loss_frac', 'norm_S', 'norm_O')])
        ok = [r for r in rows if None not in r]
        if ok:
            arr = np.array(ok)
            phase[c] = dict(loss_frac=float(np.median(arr[:, 0])), norm_S=float(np.median(arr[:, 1])), norm_O=float(np.median(arr[:, 2])))
    res['phase_at_t_align'] = phase
    # описательно: t½ «я» и показатель поведения по развёртке A
    beh = [alpha([idx[(b, c)]['t_half_obj'][0] for c in SWEEP_A], [idx[(b, c)]['lam']['S'] for c in SWEEP_A]) for b in blocks]
    res['descr'] = dict(alpha_behav_self_A=beh, median_alpha_behav_self_A=float(np.median([x for x in beh if x is not None])) if any(x is not None for x in beh) else None,
                        t_align={c: t(c) for c in d['conds']}, lam_max={c: lm(c) for c in d['conds']},
                        t_half_self={c: [idx[(b, c)]['t_half_obj'][0] for b in blocks] for c in d['conds']},
                        perm_vs_init_min_gap=float(min(m['cka0'] - m['perm_max'] for m in M)))
    if not method_ok:                    # провал метода снимает каждый из P1…P4 и правило формы (совет 50, п. 2)
        for p in ('P1', 'P2', 'P3', 'P4', 'shape'):
            res[p]['verdict_raw'] = res[p]['verdict']
            res[p]['verdict'] = 'не определено (проверка метода)'
    res['verdicts'] = {p: res[p]['verdict'] for p in ('P1', 'P2', 'P3', 'P4', 'shape')}
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
    sh = res['shape']
    print(f"правило формы (вес 0): {sh['verdict']}  за кратность {sh['k_mult']}, за сигнал {sh['k_signal']} из {sh['n_defined']} | "
          f"медианы Δ_low {sh['median_delta_low']}, Δ_high {sh['median_delta_high']}")
    print('общий порог (описательно):', res['common_threshold']['P2'], res['common_threshold']['P3'])
    print('фаза в момент t_align (медианы):', {c: {k: round(v, 3) for k, v in x.items()} for c, x in res['phase_at_t_align'].items()})
    print('вердикт:', res['verdict'])


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--test']
    main(args[0], args[1], test='--test' in sys.argv)
