#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-01: анализ и вердикты по PREREG (редакция после совета 48). python3 analyze_spectrum01.py RESULTS.json OUT.json
Группа = блок × q × режим × помехи (d_nuis, extra). Меры группы:
  cka0, ckaT — средняя по 6 парам CKA на половине B в шаге 0 и в конце; d_cka = ckaT − cka0;
  t_align — время, когда средняя CKA половины B впервые достигает порога cka0_A + ½·(ckaT_A − cka0_A), порог по половине A
            (линейная интерполяция между точками записи); только при d_cka ≥ 0,1; флаг, если пересечение на шаге 0;
  behavT, r2T, perm_max (максимум по 100 перестановкам и парам), mknn0, mknnT, t½ объектов, λ кластеров (теория SELF-02).
Главное правило (несёт вес):
  P3 — богатый режим, q = 1 против q0_d64 (оба входа 64): t_align определено не меньше чем в 9 блоках (неопределённое —
       неуспех), t_align(q0_d64) > t_align(q = 1) не меньше чем в 9 из 10, и |медиана(отношение/теория) − 1| ≤ 0,10, где
       отношение = t_align(q0_d64)/t_align(q = 1), теория = √(λ_S(q = 1)/λ_max(q = 0)) того же блока.
       Опровержение: |медиана(отношение/теория) − 1| > 0,25 или q0_d64 строго раньше q = 1 не меньше чем в 9 из 10.
       Иначе — «не решено». Вторично (выбрано по пилоту): медиана отношения в [1,05; 1,40]. Описательно — то же с q = 0 (вход 62).
Проверки метода (вес 0, без номинального нуля):
  P1a (q = 1), P1b (q = 0): d_cka(богатый) − d_cka(ленивый) ≥ 0,2 не меньше чем в 9 из 10;
  P2 (q = 1): ленивый — поведение ≥ 0,98 и d_cka ≤ 0,1 не меньше чем в 9 из 10.
Описательно: перестановочный нуль против начальной линии; развёртка помех 0 / 20 / 52; кривая d_cka(t) ленивого режима;
проверка «при q = 1 λ_S наибольшая»."""
import json
import sys

import numpy as np

THR_DIFF, THR_LAZY_D, THR_BEHAV = 0.2, 0.1, 0.98
TOL_OK, TOL_BAD = 0.10, 0.25
RATIO_LO, RATIO_HI = 1.05, 1.40
NEED = 9


def crossing(steps, curve, thr):
    if curve[0] >= thr:
        return float(steps[0])
    for i in range(1, len(curve)):
        if curve[i] >= thr > curve[i - 1]:
            return float(steps[i - 1] + (thr - curve[i - 1]) / (curve[i] - curve[i - 1]) * (steps[i] - steps[i - 1]))
    return None


def t_half_obj(steps, r2, ref):
    m = np.asarray(r2).mean(1)
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
    lam = {k: float(np.mean([t[k] for t in g['theory']])) for k in ('S', 'O', 'B')}
    traj = {str(s): float(B[list(st).index(s)] - B[0]) for s in (150, 300, 600, 1500, 3000) if s in set(st.tolist())}
    return dict(block=g['block'], q=g['q'], regime=g['regime'], d_nuis=g['d_nuis'], extra=g.get('extra', 0),
                cka0=float(B[0]), ckaT=float(B[-1]), d_cka=d, cka0_A=float(A[0]), ckaT_A=float(A[-1]), t_align=ta,
                t_align_at0=bool(ta is not None and ta == float(st[0])), behavT=float(np.mean(g['behav'][-1])),
                r2T=float(np.mean(g['r2'][-1])), perm_mean=float(np.mean([p[0] for p in g['perm']])),
                perm_max=float(max(p[2] for p in g['perm'])), mknn0=float(np.mean(g['mknn0'])), mknnT=float(np.mean(g['mknnT'])),
                t_half_obj=t_half_obj(st, g['r2'], g['ref']), lam=lam, d_cka_max=float((B - B[0]).max()), d_cka_traj=traj)


def boot_ci(v, seed=11, reps=10000, stat=np.median):
    v = np.asarray(v, float)
    if not len(v):
        return None
    g = np.random.default_rng(seed)
    bs = [stat(v[g.integers(0, len(v), len(v))]) for _ in range(reps)]
    return [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


def p3(get, blocks, cond0):
    """cond0 — (d_nuis, extra) условия q = 0; q = 1 всегда (52, 0)."""
    t1 = [get(b, 1.0, 'rich', 52, 0)['t_align'] for b in blocks]
    t0 = [get(b, 0.0, 'rich', *cond0)['t_align'] for b in blocks]
    th = []
    for b in blocks:
        l1, l0 = get(b, 1.0, 'rich', 52, 0)['lam'], get(b, 0.0, 'rich', *cond0)['lam']
        th.append(float(np.sqrt(l1['S'] / max(l0.values()))))
    defined = [i for i in range(len(blocks)) if t1[i] is not None and t0[i] is not None]
    k = sum(t0[i] > t1[i] for i in defined)                   # q = 0 позже — в пользу гипотезы
    k_rev = sum(t0[i] < t1[i] for i in defined)               # q = 0 строго раньше — против
    ratios = [t0[i] / t1[i] for i in defined]
    rel = [t0[i] / t1[i] / th[i] for i in defined]
    med_rel = float(np.median(rel)) if rel else None
    dev = abs(med_rel - 1) if rel else None
    ok = bool(len(defined) >= NEED and k >= NEED and dev is not None and dev <= TOL_OK)
    bad = bool((dev is not None and dev > TOL_BAD) or k_rev >= NEED)
    med_ratio = float(np.median(ratios)) if ratios else None
    return dict(t_align_q1=t1, t_align_q0=t0, theory=th, n_defined=len(defined), k=k, k_rev=k_rev, ratios=ratios,
                rel=rel, median_ratio=med_ratio, ci95_median_ratio=boot_ci(ratios), median_rel=med_rel,
                ci95_median_rel=boot_ci(rel), dev=dev, ok=ok, refuted=bad,
                verdict='подтверждено' if ok else ('опровергнуто' if bad else 'не решено'),
                secondary_interval_ok=bool(med_ratio is not None and RATIO_LO <= med_ratio <= RATIO_HI))


def main(src, dst):
    d = json.load(open(src, encoding='utf-8'))
    M = [group_measures(g) for g in d['groups']]
    idx = {(m['block'], m['q'], m['regime'], m['d_nuis'], m['extra']): m for m in M}
    get = lambda b, q, rg, nz, ex: idx.get((b, q, rg, nz, ex))
    blocks = sorted({m['block'] for m in M})
    n = len(blocks)
    res = {'blocks': n, 'measures': M}
    res['P3'] = p3(get, blocks, (52, 2))                                 # главное: q0_d64
    res['P3_q0_d62'] = p3(get, blocks, (52, 0))                          # описательно: вход 62
    res['lambda_S_max_q1'] = sum(get(b, 1.0, 'rich', 52, 0)['lam']['S'] >= max(get(b, 1.0, 'rich', 52, 0)['lam'].values()) for b in blocks)
    res['lambda_argmax_q0'] = [max(get(b, 0.0, 'rich', 52, 2)['lam'], key=get(b, 0.0, 'rich', 52, 2)['lam'].get) for b in blocks]
    for q, key in ((1.0, 'P1a'), (0.0, 'P1b')):
        diffs = [get(b, q, 'rich', 52, 0)['d_cka'] - get(b, q, 'lazy', 52, 0)['d_cka'] for b in blocks]
        k = sum(x >= THR_DIFF for x in diffs)
        res[key] = dict(q=q, diffs=diffs, k=k, n=n, ok=k >= NEED, median=float(np.median(diffs)), ci95_median=boot_ci(diffs))
    lz = [get(b, 1.0, 'lazy', 52, 0) for b in blocks]
    k2 = sum(m['behavT'] >= THR_BEHAV and m['d_cka'] <= THR_LAZY_D for m in lz)
    res['P2'] = dict(k=k2, n=n, ok=k2 >= NEED, behav=[m['behavT'] for m in lz], d_cka=[m['d_cka'] for m in lz],
                     d_cka_max=[m['d_cka_max'] for m in lz], d_cka_traj=[m['d_cka_traj'] for m in lz],
                     behav_rich=[get(b, 1.0, 'rich', 52, 0)['behavT'] for b in blocks])
    sweep = {}
    for nz in (0, 20, 52):
        for rg in ('rich', 'lazy'):
            ms = [get(b, 1.0, rg, nz, 0) for b in blocks]
            if all(ms):
                sweep[f'{rg}_{nz}'] = dict(cka0=[m['cka0'] for m in ms], ckaT=[m['ckaT'] for m in ms], d_cka=[m['d_cka'] for m in ms],
                                           mknn0=[m['mknn0'] for m in ms], mknnT=[m['mknnT'] for m in ms],
                                           perm_max=[m['perm_max'] for m in ms])
    res['descr'] = dict(sweep=sweep, perm_vs_init_min_gap=float(min(m['cka0'] - m['perm_max'] for m in M)),
                        t_align_at0_any=any(m['t_align_at0'] for m in M),
                        t_align_lt_t_half_self=[(m['t_align'], m['t_half_obj'][0]) for m in M if m['regime'] == 'rich' and m['d_nuis'] == 52])
    method_ok = res['P1a']['ok'] and res['P2']['ok']
    res['verdicts'] = {k: ('подтверждено' if res[k]['ok'] else 'не подтверждено') for k in ('P1a', 'P1b', 'P2')}
    res['verdicts']['P3'] = res['P3']['verdict']
    if not method_ok:
        res['verdict'] = 'не определено: проверка метода (P1a или P2) не прошла'
    elif res['P3']['verdict'] == 'подтверждено':
        res['verdict'] = 'гипотеза подтверждена: время появления сходства в богатом режиме масштабируется как 1/√λ_max (в пределах 10 %)'
    elif res['P3']['verdict'] == 'опровергнуто':
        res['verdict'] = 'гипотеза опровергнута'
    else:
        res['verdict'] = 'не решено'
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    p = res['P3']
    print(f"P3 (q0_d64): {p['verdict']}  определено {p['n_defined']}/{n}, позже {p['k']}, раньше {p['k_rev']}, "
          f"медиана отношения {p['median_ratio']}, отношение/теория {p['median_rel']}, вторичное {p['secondary_interval_ok']}")
    q = res['P3_q0_d62']
    print(f"P3 (q = 0, вход 62, описательно): {q['verdict']}  медиана отношения {q['median_ratio']}, отношение/теория {q['median_rel']}")
    for kk in ('P1a', 'P1b', 'P2'):
        print(f"{kk} (метод): {res['verdicts'][kk]}  k={res[kk]['k']}/{n}")
    print('λ_S наибольшая при q = 1:', res['lambda_S_max_q1'], '| аргмакс λ при q = 0:', res['lambda_argmax_q0'])
    print('вердикт:', res['verdict'])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
