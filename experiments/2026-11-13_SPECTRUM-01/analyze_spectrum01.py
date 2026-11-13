#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-01: анализ и вердикты по PREREG. python3 analyze_spectrum01.py RESULTS.json OUT.json
Меры блока (группа = блок × q × режим × помехи):
  cka0, ckaT — средняя по 6 парам CKA на половине B в шаге 0 и в конце; d_cka = ckaT − cka0;
  t_align — время, когда средняя CKA половины B впервые достигает порога cka0_A + ½·(ckaT_A − cka0_A)
            по половине A (линейная интерполяция между точками записи); только при d_cka ≥ 0,1;
  behavT — среднее сходство поведения в конце; r2T — средний R² объектов в конце;
  perm_max — наибольшее значение перестановочного нуля по парам; mknn0, mknnT.
Правила (PREREG §5):
  P1a (q = 1) и P1b (q = 0): d_cka(богатый) − d_cka(ленивый) ≥ 0,2 не меньше чем в 9 из 10 блоков;
  P2 (q = 1): в ленивом режиме behavT ≥ 0,98 и d_cka ≤ 0,1 не меньше чем в 9 из 10;
  P3 (богатый): t_align(q = 0) > t_align(q = 1) не меньше чем в 9 из 10 и медиана отношения t_align(0)/t_align(1)
      в [1,05; 1,40];
  P4 (метод): cka0 ≥ perm_max + 0,3 во всех группах блока (основные и контроль) не меньше чем в 9 из 10 блоков;
      и без помех cka0 ≥ 0,75 не меньше чем в 9 из 10 (сходство необученных сетей от геометрии входа)."""
import json
import sys
from math import comb

import numpy as np

THR_DIFF, THR_LAZY_D, THR_BEHAV, RATIO_LO, RATIO_HI, THR_PERM, THR_CTRL = 0.2, 0.1, 0.98, 1.05, 1.40, 0.3, 0.75
NEED = 9


def binom_sf(k, n, p=0.5):
    return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


def crossing(steps, curve, thr):
    if curve[0] >= thr:
        return float(steps[0])
    for i in range(1, len(curve)):
        if curve[i] >= thr > curve[i - 1]:
            return float(steps[i - 1] + (thr - curve[i - 1]) / (curve[i] - curve[i - 1]) * (steps[i] - steps[i - 1]))
    return None


def t_half_obj(steps, r2, ref):
    """Первый шаг записи, на котором R² объекта (среднее по сетям) достигает ½ среднего потолка OLS."""
    m = np.asarray(r2).mean(1)                   # [t, объект]
    rf = np.asarray(ref).mean(0)
    out = []
    for o in range(5):
        hit = np.nonzero(m[:, o] >= 0.5 * rf[o])[0]
        out.append(int(steps[hit[0]]) if len(hit) else None)
    return out


def group_measures(g):
    st = np.array(g['step'])
    A, B = np.array(g['ckaA']).mean(1), np.array(g['ckaB']).mean(1)
    d = float(B[-1] - B[0])
    thr = A[0] + 0.5 * (A[-1] - A[0])
    ta = crossing(st, B, thr) if d >= THR_LAZY_D else None
    return dict(block=g['block'], q=g['q'], regime=g['regime'], d_nuis=g['d_nuis'], cka0=float(B[0]), ckaT=float(B[-1]),
                d_cka=d, cka0_A=float(A[0]), ckaT_A=float(A[-1]), t_align=ta, behavT=float(np.mean(g['behav'][-1])),
                r2T=float(np.mean(g['r2'][-1])), perm_mean=float(np.mean([p[0] for p in g['perm']])),
                perm_max=float(max(p[2] for p in g['perm'])), mknn0=float(np.mean(g['mknn0'])), mknnT=float(np.mean(g['mknnT'])),
                t_half_obj=t_half_obj(st, g['r2'], g['ref']),
                theory_S=float(np.mean([t['S'] for t in g['theory']])), theory_O=float(np.mean([t['O'] for t in g['theory']])),
                theory_B=float(np.mean([t['B'] for t in g['theory']])))


def boot_ci(v, seed=11, reps=10000, stat=np.median):
    v = np.asarray(v, float)
    g = np.random.default_rng(seed)
    bs = [stat(v[g.integers(0, len(v), len(v))]) for _ in range(reps)]
    return [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


def main(src, dst):
    d = json.load(open(src, encoding='utf-8'))
    M = [group_measures(g) for g in d['groups']]
    get = lambda b, q, rg, nz: next((m for m in M if m['block'] == b and m['q'] == q and m['regime'] == rg and m['d_nuis'] == nz), None)
    nz = d['d_nuis']
    blocks = sorted({m['block'] for m in M})
    n = len(blocks)
    res = {'blocks': n, 'measures': M}
    for q, key in ((1.0, 'P1a'), (0.0, 'P1b')):
        diffs = [get(b, q, 'rich', nz)['d_cka'] - get(b, q, 'lazy', nz)['d_cka'] for b in blocks]
        k = sum(x >= THR_DIFF for x in diffs)
        res[key] = dict(q=q, diffs=diffs, k=k, n=n, ok=k >= NEED, p_sign_ge_k=binom_sf(k, n), median=float(np.median(diffs)),
                        ci95_median=boot_ci(diffs))
    lz = [get(b, 1.0, 'lazy', nz) for b in blocks]
    k2 = sum(m['behavT'] >= THR_BEHAV and m['d_cka'] <= THR_LAZY_D for m in lz)
    res['P2'] = dict(k=k2, n=n, ok=k2 >= NEED, behav=[m['behavT'] for m in lz], d_cka=[m['d_cka'] for m in lz],
                     behav_rich=[get(b, 1.0, 'rich', nz)['behavT'] for b in blocks])
    t1 = [get(b, 1.0, 'rich', nz)['t_align'] for b in blocks]
    t0 = [get(b, 0.0, 'rich', nz)['t_align'] for b in blocks]
    ok_pairs = [(a, c) for a, c in zip(t0, t1) if a is not None and c is not None]
    k3 = sum(a > c for a, c in ok_pairs)
    ratios = [a / c for a, c in ok_pairs]
    th = [float(np.sqrt(get(b, 1.0, 'rich', nz)['theory_S'] / get(b, 0.0, 'rich', nz)['theory_S'])) for b in blocks]
    med = float(np.median(ratios)) if ratios else None
    res['P3'] = dict(k=k3, n=n, n_defined=len(ok_pairs), t_align_q1=t1, t_align_q0=t0, ratios=ratios, median_ratio=med,
                     ci95_median=boot_ci(ratios) if ratios else None, theory_sqrt_lambdaS=th, median_theory=float(np.median(th)),
                     ok=bool(k3 >= NEED and med is not None and RATIO_LO <= med <= RATIO_HI), p_sign_ge_k=binom_sf(k3, n))
    k4a = sum(all(m['cka0'] >= m['perm_max'] + THR_PERM for m in M if m['block'] == b) for b in blocks)
    ctrl = [get(b, 1.0, 'rich', 0) for b in blocks]
    have_ctrl = all(c is not None for c in ctrl)
    k4b = sum(c['cka0'] >= THR_CTRL for c in ctrl) if have_ctrl else 0
    res['P4'] = dict(k_perm=k4a, k_ctrl=k4b, n=n, ok=bool(k4a >= NEED and have_ctrl and k4b >= NEED),
                     cka0_ctrl=[c['cka0'] for c in ctrl] if have_ctrl else None,
                     cka0_main=[get(b, 1.0, 'rich', nz)['cka0'] for b in blocks])
    res['false_level_rule_9of10'] = binom_sf(NEED, n)
    res['verdicts'] = {
        'P1a': 'подтверждено' if res['P1a']['ok'] else 'не подтверждено',
        'P1b': 'подтверждено' if res['P1b']['ok'] else 'не подтверждено',
        'P2': 'подтверждено' if res['P2']['ok'] else 'не подтверждено',
        'P3': 'подтверждено' if res['P3']['ok'] else 'не подтверждено',
        'P4': 'подтверждено' if res['P4']['ok'] else 'не подтверждено'}
    hyp = res['P1a']['ok'] and res['P2']['ok'] and res['P3']['ok']
    refuted = (not res['P1a']['ok'] and np.median(res['P1a']['diffs']) <= 0) or (res['P3']['n_defined'] >= NEED and k3 <= n - NEED)
    res['verdict'] = ('гипотеза подтверждена: в богатом режиме представления сходятся сверх начальной линии и раньше при видимой своей команде, в ленивом — нет при том же поведении'
                      if hyp else 'гипотеза опровергнута' if refuted else 'гипотеза подтверждена частично (см. P1–P3)')
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for kk in ('P1a', 'P1b', 'P2', 'P3', 'P4'):
        r = res[kk]
        extra = (f" медиана разности {r['median']:.3f}" if kk.startswith('P1') else
                 f" медиана отношения {r['median_ratio']} (теория {r['median_theory']:.3f})" if kk == 'P3' else '')
        print(f"{kk}: {res['verdicts'][kk]}  k={r.get('k', r.get('k_perm'))}/{n}{extra}")
    print('вердикт:', res['verdict'])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
