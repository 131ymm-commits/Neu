#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCGEO-01: анализ теста по PREREG §5. python3 analyze_ocgeo_test.py OUT_DIR RESULT.json
OUT_DIR — вывод ocgeo_extract_test.py (answers.json, nbrs_*.npz). Оценщики, калибровка и выбор головы — analyze_ocgeo.py.
Настройка GEO закреплена по пилоту 1: слой — ближайший к ¼ глубины, k = 50 (лучший ИОИ GEO на сетке 4 × 4 пилота).
GEO0 и INPUT — с тем же k. Калибровка — изотоническая регрессия по задачам ID теста; цели — задачи OOD теста.
Правила (вес несут P1–P3; бутстреп по задачам OOD, 10 000 повторов, зерно 808; калибровка закреплена; ДИ 99 % —
ложный уровень каждого правила 0,005 на сторону, серии из трёх — не выше 0,015):
  P1 (гипотеза описи): Δ1 = ИОИ(GEO) − ИОИ(AGREE). Подтверждено — верхняя граница ДИ 99 % < 0; опровергнуто — нижняя > 0.
  P2: Δ2 = ИОИ(AGREE) − ИОИ(CONF). Подтверждено (согласие голов лучше уверенности) — верхняя граница < 0; опровергнуто —
      нижняя > 0.
  P3: Δ3 = средняя по 5 головам разность AUROC на OOD: GEO − GEO0 (геометрия головы сверх необученной). Подтверждено —
      нижняя граница ДИ 99 % > 0; опровергнуто — верхняя < 0. Бутстреп — 2000 повторов (зерно 809).
  Иначе — «не решено».
Проверки метода (вес 0; провал любой → каждый из P1–P3 «не определено (проверка метода)»): загружены все 5 голов и step0;
  у каждой головы на ID и на OOD не меньше 20 верных и 20 неверных ответов (иначе AUROC и калибровка вырождены).
Описательно: T, C, незнание, самообман и ИОИ каждого оценщика; AUROC по головам; GEO против INPUT; лучшая голова без
  оценщика; доля задач OOD, где верна хоть одна голова."""
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


def ioi(t, c):
    T, C = t.mean(-1), c.mean(-1)
    return (1 - T) + np.maximum(0, C - T)


def verdict_lt0(lo, hi):
    return 'подтверждено' if hi < 0 else ('опровергнуто' if lo > 0 else 'не решено')


def main(out_dir, dst):
    d, heads, base, nb = A.load(out_dir)
    names = [h['model'] for h in heads]
    errors = [f"{h['model']}_{h['revision']}" for h in d['heads'] if 'error' in h]
    S, corr, rid = A.scores(d, heads, base, nb, GEO_F, GEO_K)
    tgt = ~rid
    cols = np.nonzero(tgt)[0]
    sel, per_head, cal_all = {}, {}, {}
    for e in EVALS:
        M = S[e]
        cal = np.zeros_like(M, dtype=float)
        for i in range(len(heads)):
            iso = IsotonicRegression(out_of_bounds='clip', y_min=0, y_max=1).fit(M[i][rid], corr[i][rid].astype(float))
            cal[i] = iso.predict(M[i])
        pick = cal[:, tgt].argmax(0)
        sel[e] = (corr[pick, cols].astype(float), cal[pick, cols], np.bincount(pick, minlength=len(heads)).tolist())
        per_head[e] = [dict(head=names[i], auroc_ood=A.auroc(M[i][tgt], corr[i][tgt]), auroc_id=A.auroc(M[i][rid], corr[i][rid]),
                            claim_ood=float(cal[i][tgt].mean()), acc_ood=float(corr[i][tgt].mean())) for i in range(len(heads))]
    summ = {}
    for e in EVALS:
        t, c, picked = sel[e]
        T, C = float(t.mean()), float(c.mean())
        summ[e] = dict(T=T, C=C, ignorance=1 - T, deception=max(0.0, C - T), ioi=(1 - T) + max(0.0, C - T), picked=picked)
    g = np.random.default_rng(808)
    jj = g.integers(0, len(cols), (10000, len(cols)))
    boot = {e: ioi(sel[e][0][jj], sel[e][1][jj]) for e in EVALS}
    q = lambda a: [float(x) for x in np.percentile(a, [0.5, 50, 99.5])]                  # noqa: E731  ДИ 99 %
    d1, d2 = boot['GEO'] - boot['AGREE'], boot['AGREE'] - boot['CONF']
    P1 = dict(delta=summ['GEO']['ioi'] - summ['AGREE']['ioi'], ci99=q(d1)[::2], verdict=verdict_lt0(*q(d1)[::2]))
    P2 = dict(delta=summ['AGREE']['ioi'] - summ['CONF']['ioi'], ci99=q(d2)[::2], verdict=verdict_lt0(*q(d2)[::2]))
    # P3: средняя по головам разность AUROC OOD (GEO − GEO0)
    g3 = np.random.default_rng(809)
    Y = corr[:, cols]
    SG, S0 = S['GEO'][:, cols], S['GEO0'][:, cols]

    def mean_diff(ix):
        vals = []
        for i in range(len(heads)):
            a1, a0 = A.auroc(SG[i][ix], Y[i][ix]), A.auroc(S0[i][ix], Y[i][ix])
            vals.append(np.nan if a1 is None or a0 is None else a1 - a0)
        return float(np.nanmean(vals))
    est3 = mean_diff(np.arange(len(cols)))
    b3 = [mean_diff(g3.integers(0, len(cols), len(cols))) for _ in range(2000)]
    lo3, hi3 = np.percentile(b3, [0.5, 99.5])
    P3 = dict(delta=est3, ci99=[float(lo3), float(hi3)],
              verdict='подтверждено' if lo3 > 0 else ('опровергнуто' if hi3 < 0 else 'не решено'),
              per_head=[(per_head['GEO'][i]['auroc_ood'] or np.nan) - (per_head['GEO0'][i]['auroc_ood'] or np.nan) for i in range(len(heads))])
    # проверки метода
    counts = {names[i]: dict(id_correct=int(corr[i][rid].sum()), id_wrong=int((~corr[i][rid]).sum()),
                             ood_correct=int(corr[i][tgt].sum()), ood_wrong=int((~corr[i][tgt]).sum())) for i in range(len(heads))}
    method = dict(errors=errors, n_heads=len(heads), has_step0=base is not None, counts=counts,
                  min_each_ok=all(min(v.values()) >= MIN_EACH for v in counts.values()))
    method['ok'] = (not errors) and len(heads) == 5 and method['has_step0'] and method['min_each_ok']
    res = dict(split=d['split'], heads=names, geo_setting=dict(f=GEO_F, k=GEO_K), n_id=int(rid.sum()), n_ood=int(tgt.sum()),
               accuracy={names[i]: dict(ID=float(corr[i][rid].mean()), OOD=float(corr[i][tgt].mean())) for i in range(len(heads))},
               evaluators=summ, per_head=per_head, P1=P1, P2=P2, P3=P3, method=method,
               geo_minus_input=dict(delta=summ['GEO']['ioi'] - summ['INPUT']['ioi'], ci99=q(boot['GEO'] - boot['INPUT'])[::2]),
               any_head_correct_ood=float(corr[:, tgt].any(0).mean()))
    b = int(np.argmax(corr[:, rid].mean(1)))
    Tb, Cb = float(corr[b, tgt].mean()), float(corr[b, rid].mean())
    res['best_head_no_evaluator'] = dict(head=names[b], T=Tb, C=Cb, ioi=(1 - Tb) + max(0.0, Cb - Tb), deception=max(0.0, Cb - Tb))
    if not method['ok']:
        for p in ('P1', 'P2', 'P3'):
            res[p]['verdict_raw'] = res[p]['verdict']
            res[p]['verdict'] = 'не определено (проверка метода)'
    res['verdicts'] = {p: res[p]['verdict'] for p in ('P1', 'P2', 'P3')}
    res['verdict'] = '; '.join(f'{p}: {v}' for p, v in res['verdicts'].items())
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('точность (ID / OOD):', {n: (round(v['ID'], 3), round(v['OOD'], 3)) for n, v in res['accuracy'].items()})
    for e in EVALS:
        s = summ[e]
        print(f"{e:6s} ИОИ {s['ioi']:.4f} = незнание {s['ignorance']:.4f} + самообман {s['deception']:.4f} (T {s['T']:.4f}, C {s['C']:.4f})")
    for p in ('P1', 'P2', 'P3'):
        print(f"{p}: {res[p]['verdict']}  Δ {res[p]['delta']:.4f}, ДИ99 {[round(x, 4) for x in res[p]['ci99']]}")
    print('метод:', method['ok'], '| вердикт:', res['verdict'])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
