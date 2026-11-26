#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCSHIFT-01, разведка по трём готовым сдвигам (OCCOR-01, OCMIX-01, OCREP-01). Пост-хок: вердиктов прежних опытов не
меняет; числа отсюда — основание гипотез и мощности OCSHIFT-01, опорой не считаются.
  python3 explore_shifts.py OUT_DIR [--boot B] [--workers W] [--stub]
Считается на сторонней площадке (GitHub Actions; слово автора 15.11.2026). --stub — проверка кода на заглушках сухого
прогона OCREP-01 (числа заглушек смысла не несут).

Что считается по каждому сдвигу (части test и pilot — два набора задач одного сдвига):
  1. Базы. Точность голов; лучшая голова по ID (ONE-BEST) и её точность OOD; оракул — доля задач, где верна хоть одна голова.
  2. Восемь оценщиков (код OCCOR-01 и OCMIX-01): T, C, самообман C − T (со знаком), ИОИ, Брайер выбранной заявки — на OOD;
     то же на ID в выборке калибровки (in-sample) и на ID с кросс-подгонкой (5 частей: оценщик и калибровка — без части,
     выбор — на части). Самообман на ID — «проклятие победителя» (отбор без сдвига).
  3. Доли выбора по головам; как часто выбор совпадает с ответом ONE-BEST; точность там, где выбор от неё отходит.
  4. ONE-BEST с заявкой каждого оценщика: T — точность лучшей головы, C — её средняя заявка.
  5. POST — вторая калибровка после отбора: изотоника «заявка выбранного ответа → его правильность» по ID
     (POST-CV — по заявкам кросс-подгонки, POST-IN — по in-sample); выбор не меняется, меняется только заявка.
  6. Согласованность заявок (без правды): на задаче сумма заявок по разным ответам не может превышать 1.
     s_max = Σ по разным ответам (наибольшая заявка среди давших ответ); доля задач с s_max > 1, средний избыток;
     COHERE — заявка выбранного ответа, делённая на max(1, s_max).
  7. Правила выбора оценщика без правды: MIN-C — оценщик с наименьшей средней заявкой выбранных ответов на OOD;
     MIN-EXCESS — с наименьшим средним избытком согласованности.
  8. Слияния CONF и LR-AGREE на уровне заявок: FUSE-MIN (минимум двух заявок головы), FUSE-MEAN (среднее).
  9. Сдвиг матрицы попарных совпадений ответов ID → OOD (без правды); верхняя граница средней точности голов из
     несогласия (доля наибольшей группы одинаковых ответов) против средней заявки.
 10. Вложенный бутстреп (B повторов, зерно 1502): стандартные ошибки и ДИ 99 % ключевых разностей ИОИ."""
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np
from sklearn.isotonic import IsotonicRegression

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, '2026-11-15_OCREP-01'))
import analyze_ocrep as Q  # noqa: E402

Z, M, T = Q.Z, Q.M, Q.Z.T
EVALS = Q.EVALS
SHIFTS = [('OCCOR-01', '2026-11-14_OCCOR-01'), ('OCMIX-01', '2026-11-14_OCMIX-01'), ('OCREP-01', '2026-11-15_OCREP-01')]
PARTS = [('test', os.path.join('run', 'out')), ('pilot', os.path.join('pilot', 'out'))]
K_CV, SEED_CV, SEED_BOOT = 5, 1501, 1502
SETS = {'pair': ('CONF', 'LR-AGREE'), 'six': ('AGREE', 'NB-AGREE', 'LR-AGREE', 'NB-IND', 'FAM-AGREE', 'CONF'), 'all8': EVALS}
DIFFS = [('CONF', 'LR-AGREE'), ('LR-AGREE', 'AGREE'), ('CONF', 'AGREE'), ('LR-AGREE', 'NB-IND'), ('ONE-BEST', 'CONF'), ('ONE-BEST', 'LR-AGREE'),
         ('ONE-BEST', 'AGREE'), ('MIN-C pair', 'CONF'), ('MIN-C pair', 'LR-AGREE'), ('MIN-C all8', 'CONF'), ('MIN-C all8', 'LR-AGREE'),
         ('POST-IN CONF', 'CONF'), ('POST-IN LR-AGREE', 'LR-AGREE'), ('POST-IN AGREE', 'AGREE'), ('POST-IN CONF', 'POST-IN LR-AGREE'),
         ('ONE-BEST', 'POST-IN CONF'), ('ONE-BEST', 'POST-IN LR-AGREE')]


def select(cal, y):
    """Выбор — наибольшая заявка, ничья «поровну» (как analyze_ocgeo_test.select). Возвращает t, c и веса голов."""
    mx = cal.max(0)
    tied = np.abs(cal - mx[None, :]) <= 1e-12
    w = tied / tied.sum(0)
    return (y * w).sum(0), mx, w


def meas(t, c):
    Tm, Cm = float(np.mean(t)), float(np.mean(c))
    return dict(T=Tm, C=Cm, dec=Cm - Tm, ioi=(1 - Tm) + max(0.0, Cm - Tm), brier=float(np.mean(c * c - 2 * c * t + t)))


def iso_fit(x, y):
    return IsotonicRegression(out_of_bounds='clip', y_min=0, y_max=1).fit(np.asarray(x, float), np.asarray(y, float))


def coherence(cal, A_cols):
    """s_mean, s_max по задачам: сумма по разным ответам средней / наибольшей заявки давших этот ответ (None — отдельно)."""
    n = cal.shape[1]
    s_mean, s_max = np.zeros(n), np.zeros(n)
    for j in range(n):
        a, c = A_cols[:, j], cal[:, j]
        for v in np.unique(a[a >= 0]):
            m = a == v
            s_mean[j] += c[m].mean()
            s_max[j] += c[m].max()
        s_mean[j] += c[a < 0].sum()
        s_max[j] += c[a < 0].sum()
    return s_mean, s_max


def point(ans, corr, rid, logp, fam, names):
    H = len(names)
    allh = list(range(H))
    idi, ood = np.nonzero(rid)[0], np.nonzero(~rid)[0]
    ag = Q.agree_matrix(ans)
    A_ = np.array([[-1 if x is None else x for x in a] for a in ans])
    y_o, y_i = corr[:, ood].astype(float), corr[:, idi].astype(float)
    acc_id, acc_ood = corr[:, idi].mean(1), corr[:, ood].mean(1)
    hb = int(np.argmax(acc_id))
    res = dict(n_id=int(len(idi)), n_ood=int(len(ood)), heads=names,
               accuracy={names[k]: dict(id=float(acc_id[k]), ood=float(acc_ood[k])) for k in allh},
               one_best=dict(head=names[hb], acc_id=float(acc_id[hb]), acc_ood=float(acc_ood[hb]),
                             best_ood_head=names[int(np.argmax(acc_ood))], best_ood_acc=float(acc_ood.max())),
               oracle=dict(id=float(corr[:, idi].any(0).mean()), ood=float(corr[:, ood].any(0).mean())),
               mean_head_acc=dict(id=float(acc_id.mean()), ood=float(acc_ood.mean())))
    # сдвиг матрицы совпадений и граница из несогласия (без правды)
    A_id, A_ood = ag[:, :, idi].mean(2), ag[:, :, ood].mean(2)
    off = ~np.eye(H, dtype=bool)
    res['agree_shift'] = dict(mean_abs=float(np.abs(A_ood - A_id)[off].mean()), max_abs=float(np.abs(A_ood - A_id)[off].max()),
                              mean_id=float(A_id[off].mean()), mean_ood=float(A_ood[off].mean()))

    def largest_group(cols):
        out = np.zeros(len(cols))
        for k, j in enumerate(cols):
            a = A_[:, j]
            a = a[a >= 0]
            out[k] = (np.unique(a, return_counts=True)[1].max() / H) if len(a) else 0.0
        return out
    lg_o, lg_i = largest_group(ood), largest_group(idi)
    res['disagreement_bound'] = dict(id=float(lg_i.mean()), ood=float(lg_o.mean()))
    # оценщики
    S = Q.scores(ag, corr, logp, allh, idi, fam, EVALS)
    g = np.random.default_rng(SEED_CV)
    perm = g.permutation(len(idi))
    folds = [np.sort(perm[k::K_CV]) for k in range(K_CV)]                      # позиции в idi
    cv_t, cv_c = {e: np.zeros(len(idi)) for e in EVALS}, {e: np.zeros(len(idi)) for e in EVALS}
    for k in range(K_CV):
        te = idi[folds[k]]
        tr = idi[np.sort(np.concatenate([folds[m] for m in range(K_CV) if m != k]))]
        Sk = Q.scores(ag, corr, logp, allh, tr, fam, EVALS)
        for e in EVALS:
            t, c, _ = select(T.calibrate(Sk[e], corr, tr, te), corr[:, te].astype(float))
            cv_t[e][folds[k]], cv_c[e][folds[k]] = t, c
    ev, cal_o = {}, {}
    same_bh = (A_[:, ood] == A_[hb, ood][None, :]) & (A_[:, ood] >= 0)
    for e in EVALS:
        co = T.calibrate(S[e], corr, idi, ood)
        ci_ = T.calibrate(S[e], corr, idi, idi)
        cal_o[e] = co
        t, c, w = select(co, y_o)
        ti, ci, _ = select(ci_, y_i)
        r = dict(ood=meas(t, c), id_insample=meas(ti, ci), id_crossfit=meas(cv_t[e], cv_c[e]),
                 share={names[k]: float(w[k].mean()) for k in allh}, top10=Z.top_frac(c, t),
                 claim_all_pairs=dict(id=float(ci_.mean()), ood=float(co.mean())))
        on_bh = (w * same_bh).sum(0)                                            # вес выбора на ответе ONE-BEST
        sw = 1 - on_bh
        r['vs_one_best'] = dict(same_answer=float(on_bh.mean()), switch=float(sw.mean()),
                                T_selected_on_switch=float((w * ~same_bh * y_o).sum() / max(sw.sum(), 1e-12)),
                                T_one_best_on_switch=float((sw * y_o[hb]).sum() / max(sw.sum(), 1e-12)))
        r['one_best'] = meas(y_o[hb], co[hb])
        c_cv, c_in = iso_fit(cv_c[e], cv_t[e]).predict(c), iso_fit(ci, ti).predict(c)
        r['post_cv'], r['post_in'] = meas(t, c_cv), meas(t, c_in)
        r['post_cv_top10'] = Z.top_frac(c_cv, t)
        sm_o, sx_o = coherence(co, A_[:, ood])
        sm_i, sx_i = coherence(ci_, A_[:, idi])
        viol = sx_o > 1 + 1e-9
        r['coherence'] = dict(
            ood=dict(s_max=float(sx_o.mean()), s_mean=float(sm_o.mean()), frac_viol=float(viol.mean()), excess=float(np.maximum(0, sx_o - 1).mean())),
            id=dict(s_max=float(sx_i.mean()), s_mean=float(sm_i.mean()), frac_viol=float((sx_i > 1 + 1e-9).mean()), excess=float(np.maximum(0, sx_i - 1).mean())),
            ood_viol=dict(n=int(viol.sum()), C=float(c[viol].mean()) if viol.any() else None, T=float(t[viol].mean()) if viol.any() else None),
            ood_ok=dict(n=int((~viol).sum()), C=float(c[~viol].mean()) if (~viol).any() else None, T=float(t[~viol].mean()) if (~viol).any() else None))
        r['cohere'] = meas(t, c / np.maximum(1.0, sx_o))
        ev[e] = r
    res['evaluators'] = ev
    for name, f in (('FUSE-MIN', np.minimum), ('FUSE-MEAN', lambda a, b: 0.5 * (a + b))):
        t, c, w = select(f(cal_o['CONF'], cal_o['LR-AGREE']), y_o)
        res.setdefault('fusions', {})[name] = dict(ood=meas(t, c), share={names[k]: float(w[k].mean()) for k in allh})
    res['meta'] = {}
    for sname, es in SETS.items():
        byC = min(es, key=lambda e: ev[e]['ood']['C'])
        byX = min(es, key=lambda e: ev[e]['coherence']['ood']['excess'])
        best_ioi, best_br = min(es, key=lambda e: ev[e]['ood']['ioi']), min(es, key=lambda e: ev[e]['ood']['brier'])
        res['meta'][sname] = dict(min_C=byC, min_C_ioi=ev[byC]['ood']['ioi'], min_C_brier=ev[byC]['ood']['brier'],
                                  min_excess=byX, min_excess_ioi=ev[byX]['ood']['ioi'],
                                  best_ioi=best_ioi, best_ioi_value=ev[best_ioi]['ood']['ioi'], best_brier=best_br,
                                  best_brier_value=ev[best_br]['ood']['brier'],
                                  worst_ioi_value=max(ev[e]['ood']['ioi'] for e in es))
    return res


_ST = {}


def _init(st):
    _ST.clear()
    _ST.update(st)


def _init_worker(st):
    from threadpoolctl import threadpool_limits
    threadpool_limits(1)
    _init(st)


def _rep(fc):
    """Один повтор вложенного бутстрепа: ИОИ оценщиков, ONE-BEST (заявка CONF), POST-IN, MIN-C."""
    s = _ST
    ag, corr, logp, fam, allh = s['ag'], s['corr'], s['logp'], s['fam'], s['allh']
    fit, cols = fc
    S = Q.scores(ag, corr, logp, allh, fit, fam, EVALS)
    y_c, y_f = corr[:, cols].astype(float), corr[:, fit].astype(float)
    out, Cs = {}, {}
    for e in EVALS:
        co = T.calibrate(S[e], corr, fit, cols)
        t, c, _ = select(co, y_c)
        m = meas(t, c)
        out[e], Cs[e] = m['ioi'], m['C']
        out['T ' + e], out['dec ' + e] = m['T'], m['dec']
        if e in ('CONF', 'LR-AGREE', 'AGREE'):
            ti, ci, _ = select(T.calibrate(S[e], corr, fit, fit), y_f)
            out['POST-IN ' + e] = meas(t, iso_fit(ci, ti).predict(c))['ioi']
            out['dec_id ' + e] = float(np.mean(ci) - np.mean(ti))
        if e == 'CONF':
            hb = int(np.argmax(corr[:, fit].mean(1)))
            out['ONE-BEST'] = meas(y_c[hb], co[hb])['ioi']
    for sname in ('pair', 'all8'):
        out['MIN-C ' + sname] = out[min(SETS[sname], key=lambda e: Cs[e])]
    return out


def boot(ans, corr, rid, logp, fam, names, B, workers, seed):
    idi, ood = np.nonzero(rid)[0], np.nonzero(~rid)[0]
    st = dict(ag=Q.agree_matrix(ans), corr=corr, logp=logp, fam=fam, allh=list(range(len(names))))
    g = np.random.default_rng(seed)
    draws = [(g.choice(idi, len(idi)), g.choice(ood, len(ood))) for _ in range(B)]
    if workers <= 1:
        _init(st)
        reps = [_rep(x) for x in draws]
    else:
        with mp.get_context('fork').Pool(workers, initializer=_init_worker, initargs=(st,)) as pool:
            reps = pool.map(_rep, draws, chunksize=max(1, B // (8 * workers)))
    keys = list(reps[0])
    V = {k: np.array([r[k] for r in reps]) for k in keys}
    out = dict(B=B, sd={k: float(V[k].std(ddof=1)) for k in keys}, mean={k: float(V[k].mean()) for k in keys}, diffs={})
    for a, b in DIFFS:
        d = V[a] - V[b]
        out['diffs'][f'{a} − {b}'] = dict(boot_mean=float(d.mean()), sd=float(d.std(ddof=1)), ci99=[float(x) for x in np.quantile(d, (0.005, 0.995))],
                                           share_below_0=float(np.mean(d < 0)))
    return out


def main(out_dir, B, workers, stub):
    os.makedirs(out_dir, exist_ok=True)
    res = dict(note='пост-хок по данным OCCOR-01, OCMIX-01, OCREP-01; вердиктов не меняет; опорой не считается', B=B, shifts={})
    if stub:
        todo = [('STUB-clones', os.path.join(EXP, '2026-11-15_OCREP-01', 'dry', 'clones'), 'stub'),
                ('STUB-indep', os.path.join(EXP, '2026-11-15_OCREP-01', 'dry', 'indep'), 'stub')]
    else:
        todo = [(name, os.path.join(EXP, d, sub), part) for name, d in SHIFTS for part, sub in PARTS]
    for k, (name, path, part) in enumerate(todo):
        t0 = time.time()
        d, heads = Q.load(path)
        ans, corr, rid, logp = Q.arrays(d, heads)
        names, fam = [Q.label(h) for h in heads], [Q.family(h) for h in heads]
        r = point(ans, corr, rid, logp, fam, names)
        r['task'] = d.get('task')
        t1 = time.time()
        if B > 0:
            r['boot'] = boot(ans, corr, rid, logp, fam, names, B, workers, SEED_BOOT + k)
        r['seconds'] = dict(point=round(t1 - t0, 1), boot=round(time.time() - t1, 1))
        res['shifts'].setdefault(name, {})[part] = r
        e = r['evaluators']
        print(f"== {name} / {part}: ID {r['n_id']}, OOD {r['n_ood']}; ONE-BEST {r['one_best']['head']} точность OOD {r['one_best']['acc_ood']:.3f}; "
              f"оракул OOD {r['oracle']['ood']:.3f}; время {r['seconds']}", flush=True)
        print('   оценщик     T     C    dec   ИОИ  Брайер | ID in: dec | ID cv: dec |  POST-CV ИОИ | COHERE ИОИ | ONE-BEST ИОИ | совп. с ONE-BEST')
        for x in EVALS:
            o = e[x]['ood']
            print(f"   {x:10s} {o['T']:.3f} {o['C']:.3f} {o['dec']:+.3f} {o['ioi']:.3f} {o['brier']:.3f} |   {e[x]['id_insample']['dec']:+.3f}   |"
                  f"   {e[x]['id_crossfit']['dec']:+.3f}   |    {e[x]['post_cv']['ioi']:.3f}     |   {e[x]['cohere']['ioi']:.3f}    |    "
                  f"{e[x]['one_best']['ioi']:.3f}     |  {e[x]['vs_one_best']['same_answer']:.3f}", flush=True)
        print('   слияния:', {n_: round(v['ood']['ioi'], 3) for n_, v in r['fusions'].items()}, '| MIN-C:', {s_: (v['min_C'], round(v['min_C_ioi'], 3), 'лучший', v['best_ioi'], round(v['best_ioi_value'], 3)) for s_, v in r['meta'].items()})
        if B > 0:
            for kk, v in r['boot']['diffs'].items():
                print(f"   Δ {kk:34s} sd {v['sd']:.4f} ДИ99 [{v['ci99'][0]:+.4f}; {v['ci99'][1]:+.4f}]")
        json.dump(res, open(os.path.join(out_dir, 'explore_shifts.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('готово', flush=True)


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], int(a[a.index('--boot') + 1]) if '--boot' in a else 0,
         int(a[a.index('--workers') + 1]) if '--workers' in a else (os.cpu_count() or 1), '--stub' in a)
