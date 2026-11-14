#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCGEO-01: анализ теста по PREREG §4 (редакция после совета 52). python3 analyze_ocgeo_test.py OUT_DIR RESULT.json [--boot B]
OUT_DIR — вывод ocgeo_extract_test.py (answers.json, nbrs_*.npz). Оценки голов — analyze_ocgeo.scores.
Настройка GEO закреплена по пилоту 1: слой — ближайший к ¼ глубины, k = 50; у GEO0 и INPUT — та же доля слоя и то же k.
Калибровка — изотоническая регрессия «оценка → вероятность верного» по задачам ID, отдельно по головам и оценщикам.
Выбор головы на задаче OOD — наибольшая откалиброванная вероятность. Ничья — «поровну» (совет 52): T и C задачи усредняются
по равным головам; правило «лучшая на ID» — описательно.
Бутстреп (совет 52, п. 7) — вложенный: в каждом повторе выборка задач ID с возвращением, переподгонка калибровки, затем
выборка задач OOD; B повторов (по умолчанию 4000), зерно 808. ДИ 99 %.
Правила (вес несут P1 и P3; ложный уровень каждого исхода 0,005, серии из двух — не выше 0,01):
  P1 (гипотеза описи): Δ1 = ИОИ(GEO) − ИОИ(AGREE). Подтверждено — верхняя граница ДИ < 0; опровергнуто — нижняя > 0.
  P3 (геометрия сверх необученной модели): Δ3 — средняя по 5 головам разность AUROC на OOD, GEO − GEO0. Подтверждено —
      нижняя граница ДИ > 0; опровергнуто — верхняя < 0. Бутстреп по задачам OOD (AUROC от калибровки не зависит), 2000, зерно 809.
  Иначе — «не решено».
Описательно (вес 0): P2 — Δ2 = ИОИ(AGREE) − ИОИ(CONF) с ДИ 99 % (мощность мала, совет 52, п. 4); GEO − INPUT;
  самообман при жёстком отборе — верхние 10 % пар (голова, задача OOD) по откалиброванной вероятности (совет 52, п. 8);
  AGREE без двойников — головы 1.4b, 2.8b, 6.9b (совет 52, п. 9); кривая по подмножествам голов 2–5; сетка 4 × 4 слой × k.
Проверки метода (провал любой → P1 и P3 «не определено (проверка метода)»): загружены 5 голов и step0; у каждой головы
  на ID и на OOD не меньше 20 верных и 20 неверных; AUROC GEO и GEO0 определён у всех голов."""
import itertools
import json
import os
import sys

import numpy as np
from sklearn.isotonic import IsotonicRegression

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_ocgeo as A  # noqa: E402

GEO_F, GEO_K = 0.25, 50
EVALS = ('GEO', 'AGREE', 'CONF', 'GEO0', 'INPUT')
MIN_EACH = 20
NO_TWINS = ['pythia-1.4b', 'pythia-2.8b', 'pythia-6.9b']


def calibrate(M, corr, fit_idx, cols):
    """Изотоническая калибровка по задачам fit_idx; предсказание на задачах cols. M, corr — (головы, задачи)."""
    out = np.zeros((M.shape[0], len(cols)))
    for i in range(M.shape[0]):
        iso = IsotonicRegression(out_of_bounds='clip', y_min=0, y_max=1).fit(M[i][fit_idx], corr[i][fit_idx].astype(float))
        out[i] = iso.predict(M[i][cols])
    return out


def select(cal, corr, rule='equal', id_acc=None):
    """cal, corr — (головы, цели). Возвращает t и c по целям и долю ничьих."""
    mx = cal.max(0)
    tied = np.abs(cal - mx[None, :]) <= 1e-12
    n_t = tied.sum(0)
    if rule == 'equal':
        t = (corr * tied).sum(0) / n_t
    else:                                                       # среди равных — лучшая по точности на ID
        rank = np.argsort(np.argsort(-np.asarray(id_acc)))      # 0 — лучшая
        score = np.where(tied, -rank[:, None], -10 ** 6)
        t = corr[score.argmax(0), np.arange(corr.shape[1])].astype(float)
    return t.astype(float), mx, float((n_t > 1).mean())


def ioi(t, c):
    T, C = float(np.mean(t)), float(np.mean(c))
    return dict(T=T, C=C, ignorance=1 - T, deception=max(0.0, C - T), ioi=(1 - T) + max(0.0, C - T))


def agree_scores(ans, heads_idx):
    """AGREE внутри подмножества голов: доля других голов подмножества с тем же ответом."""
    out = []
    for i in heads_idx:
        others = [o for o in heads_idx if o != i]
        out.append([np.mean([ans[o][j] is not None and ans[o][j] == ans[i][j] for o in others]) for j in range(len(ans[i]))])
    return np.array(out)


def main(out_dir, dst, B=4000):
    d, heads, base, nb = A.load(out_dir)
    names = [h['model'] for h in heads]
    errors = [f"{h['model']}_{h['revision']}" for h in d['heads'] if 'error' in h]
    S, corr, rid = A.scores(d, heads, base, nb, GEO_F, GEO_K)
    ans = [[r['answer'] for r in h['rows']] for h in heads]
    id_idx, ood = np.nonzero(rid)[0], np.nonzero(~rid)[0]
    id_acc = corr[:, rid].mean(1)
    corr_o = corr[:, ood]
    res = dict(split=d['split'], heads=names, geo_setting=dict(f=GEO_F, k=GEO_K), n_id=len(id_idx), n_ood=len(ood),
               load=[h.get('where') for h in heads], accuracy={names[i]: dict(ID=float(id_acc[i]), OOD=float(corr_o[i].mean())) for i in range(len(heads))})
    cal = {e: calibrate(S[e], corr, id_idx, ood) for e in EVALS}
    ev, ev_id = {}, {}
    for e in EVALS:
        t, c, tie = select(cal[e], corr_o, 'equal')
        ev[e] = dict(**ioi(t, c), tie_frac=tie)
        t2, c2, _ = select(cal[e], corr_o, 'id', id_acc)
        ev_id[e] = ioi(t2, c2)
    res['evaluators'], res['evaluators_tie_by_id'] = ev, ev_id
    # вложенный бутстреп
    g = np.random.default_rng(808)
    boot = {e: [] for e in EVALS}
    for _ in range(B):
        idb = g.choice(id_idx, len(id_idx), replace=True)
        ob = g.integers(0, len(ood), len(ood))
        for e in EVALS:
            cb = calibrate(S[e], corr, idb, ood)[:, ob]
            t, c, _ = select(cb, corr_o[:, ob], 'equal')
            boot[e].append(ioi(t, c)['ioi'])
    boot = {e: np.array(v) for e, v in boot.items()}
    ci = lambda a: [float(x) for x in np.percentile(a, [0.5, 99.5])]        # noqa: E731
    d1, d2, d4 = boot['GEO'] - boot['AGREE'], boot['AGREE'] - boot['CONF'], boot['GEO'] - boot['INPUT']
    lo1, hi1 = ci(d1)
    res['P1'] = dict(delta=ev['GEO']['ioi'] - ev['AGREE']['ioi'], ci99=[lo1, hi1],
                     verdict='подтверждено' if hi1 < 0 else ('опровергнуто' if lo1 > 0 else 'не решено'))
    res['P2_descr'] = dict(delta=ev['AGREE']['ioi'] - ev['CONF']['ioi'], ci99=ci(d2))
    res['geo_minus_input_descr'] = dict(delta=ev['GEO']['ioi'] - ev['INPUT']['ioi'], ci99=ci(d4))
    # P3
    au = {e: [A.auroc(S[e][i][ood], corr_o[i]) for i in range(len(heads))] for e in EVALS}
    p3_defined = all(x is not None for x in au['GEO'] + au['GEO0'])
    g3 = np.random.default_rng(809)

    def mean_diff(ix):
        v = []
        for i in range(len(heads)):
            a1, a0 = A.auroc(S['GEO'][i][ood][ix], corr_o[i][ix]), A.auroc(S['GEO0'][i][ood][ix], corr_o[i][ix])
            if a1 is None or a0 is None:
                return None
            v.append(a1 - a0)
        return float(np.mean(v))
    if p3_defined:
        est3 = mean_diff(np.arange(len(ood)))
        b3 = [mean_diff(g3.integers(0, len(ood), len(ood))) for _ in range(2000)]
        b3 = [x for x in b3 if x is not None]
        lo3, hi3 = ci(b3)
        res['P3'] = dict(delta=est3, ci99=[lo3, hi3], per_head=[a1 - a0 for a1, a0 in zip(au['GEO'], au['GEO0'])],
                         verdict='подтверждено' if lo3 > 0 else ('опровергнуто' if hi3 < 0 else 'не решено'))
    else:
        res['P3'] = dict(delta=None, ci99=None, per_head=None, verdict='не решено')
    res['auroc_ood'] = au
    # самообман при жёстком отборе: верхние 10 % пар (голова, задача OOD)
    top = {}
    for e in EVALS:
        flat_p, flat_y = cal[e].ravel(), corr_o.ravel()
        n10 = int(np.ceil(0.1 * len(flat_p)))
        sel = np.argsort(-flat_p, kind='mergesort')[:n10]
        acc, clm = float(flat_y[sel].mean()), float(flat_p[sel].mean())
        top[e] = dict(n=n10, accuracy=acc, claim=clm, deception=clm - acc)
    res['top10_pairs_descr'] = top
    # AGREE без двойников и кривая по подмножествам голов
    def subset_eval(sub):
        Ssub = {e: S[e][sub] for e in EVALS}
        Ssub['AGREE'] = agree_scores(ans, sub)
        out = {}
        for e in EVALS:
            cs = calibrate(Ssub[e], corr[sub], id_idx, ood)
            t, c, _ = select(cs, corr_o[sub], 'equal')
            out[e] = ioi(t, c)
        return out
    nt = [names.index(n) for n in NO_TWINS]
    res['no_twins_descr'] = dict(heads=NO_TWINS, evaluators=subset_eval(nt))
    curve = {}
    for r in range(2, len(heads) + 1):
        acc_e = {e: [] for e in EVALS}
        for sub in itertools.combinations(range(len(heads)), r):
            se = subset_eval(list(sub))
            for e in EVALS:
                acc_e[e].append((se[e]['ioi'], se[e]['deception']))
        curve[str(r)] = {e: dict(ioi=float(np.mean([x[0] for x in v])), deception=float(np.mean([x[1] for x in v])), n_subsets=len(v))
                         for e, v in acc_e.items()}
    res['subset_curve_descr'] = curve
    # сетка 4 × 4 (описательно): ИОИ GEO и средняя разность AUROC GEO − GEO0
    grid = {}
    for f in (0.25, 0.5, 0.75, 1.0):
        for k in (5, 10, 20, 50):
            Sg, cg, rg = A.scores(d, heads, base, nb, f, k)
            cgeo = calibrate(Sg['GEO'], cg, id_idx, ood)
            t, c, _ = select(cgeo, corr_o, 'equal')
            diffs = [A.auroc(Sg['GEO'][i][ood], corr_o[i]) - A.auroc(Sg['GEO0'][i][ood], corr_o[i]) for i in range(len(heads))]
            grid[f'f{f}_k{k}'] = dict(geo_ioi=ioi(t, c)['ioi'], auroc_diff_mean=float(np.mean(diffs)))
    res['grid_descr'] = grid
    # проверки метода
    counts = {names[i]: dict(id_correct=int(corr[i][rid].sum()), id_wrong=int((~corr[i][rid]).sum()),
                             ood_correct=int(corr_o[i].sum()), ood_wrong=int((~corr_o[i]).sum())) for i in range(len(heads))}
    method = dict(errors=errors, n_heads=len(heads), has_step0=base is not None, counts=counts,
                  min_each_ok=all(min(v.values()) >= MIN_EACH for v in counts.values()), auroc_defined=p3_defined)
    method['ok'] = (not errors) and len(heads) == 5 and method['has_step0'] and method['min_each_ok'] and p3_defined
    res['method'] = method
    b = int(np.argmax(id_acc))
    Tb, Cb = float(corr_o[b].mean()), float(id_acc[b])
    res['best_head_no_evaluator'] = dict(head=names[b], T=Tb, C=Cb, ioi=(1 - Tb) + max(0.0, Cb - Tb), deception=max(0.0, Cb - Tb))
    res['any_head_correct_ood'] = float(corr_o.any(0).mean())
    if not method['ok']:
        for p in ('P1', 'P3'):
            res[p]['verdict_raw'] = res[p]['verdict']
            res[p]['verdict'] = 'не определено (проверка метода)'
    res['verdicts'] = {p: res[p]['verdict'] for p in ('P1', 'P3')}
    res['verdict'] = '; '.join(f'{p}: {v}' for p, v in res['verdicts'].items())
    res['boot'] = dict(B=B, seed=808, nested=True)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('точность (ID / OOD):', {n: (round(v['ID'], 3), round(v['OOD'], 3)) for n, v in res['accuracy'].items()})
    for e in EVALS:
        s = ev[e]
        print(f"{e:6s} ИОИ {s['ioi']:.4f} = незнание {s['ignorance']:.4f} + самообман {s['deception']:.4f}  ничьих {s['tie_frac']:.3f}"
              f" | верхние 10 %: точность {top[e]['accuracy']:.3f}, заявка {top[e]['claim']:.3f}")
    print(f"P1: {res['P1']['verdict']}  Δ1 {res['P1']['delta']:.4f} ДИ99 {[round(x, 4) for x in res['P1']['ci99']]}")
    print(f"P3: {res['P3']['verdict']}  Δ3 {res['P3']['delta']} ДИ99 {res['P3']['ci99']}")
    print(f"P2 (описательно): Δ2 {res['P2_descr']['delta']:.4f} ДИ99 {[round(x, 4) for x in res['P2_descr']['ci99']]}")
    print('без двойников:', {e: round(v['ioi'], 4) for e, v in res['no_twins_descr']['evaluators'].items()})
    print('кривая подмножеств (ИОИ):', {r: {e: round(v['ioi'], 3) for e, v in x.items()} for r, x in curve.items()})
    print('метод:', method['ok'], '| вердикт:', res['verdict'])


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    B = int(sys.argv[sys.argv.index('--boot') + 1]) if '--boot' in sys.argv else 4000
    if '--boot' in sys.argv:
        args = [a for a in args if a != str(B)]
    main(args[0], args[1], B)
