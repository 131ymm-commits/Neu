#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCGEO-01, пилот 1: сжатая сводка анализа (для чтения через Google Диск, около 15 КБ текста).
python3 colab_summary.py OUT_DIR SUMMARY.txt
Оценщики и калибровка — analyze_ocgeo.py (scores, auroc). На каждой точке сетки слой × k: для каждого оценщика T, C, ИОИ,
самообман и AUROC по головам на OOD; бутстреп по задачам OOD (2000, зерно 606) — ДИ 95 % разности ИОИ: GEO минус AGREE,
CONF, GEO0, INPUT (калибровка по ID закреплена, ДИ отражает только выборку целей)."""
import json
import os
import sys

import numpy as np
from sklearn.isotonic import IsotonicRegression

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import analyze_ocgeo as A  # noqa: E402

r4 = lambda x: None if x is None else round(float(x), 4)          # noqa: E731


def main(out_dir, dst):
    d, heads, base, nb = A.load(out_dir)
    names = [h['model'] for h in heads]
    P = d['problems']
    rid = np.array([p['range'] == 'ID' for p in P])
    tgt = ~rid
    cols = np.nonzero(tgt)[0]
    corr_all = np.array([[r['correct'] for r in h['rows']] for h in heads], bool)
    S0 = dict(split=d['split'], info=d.get('info'), n_id=int(rid.sum()), n_ood=int(tgt.sum()), heads=names,
              acc={n: {'ID': r4(corr_all[i, rid].mean()), 'OOD': r4(corr_all[i, tgt].mean())} for i, n in enumerate(names)},
              any_head_correct_ood=r4(corr_all[:, tgt].any(0).mean()), grid={})
    b = int(np.argmax(corr_all[:, rid].mean(1)))
    T, C = corr_all[b, tgt].mean(), corr_all[b, rid].mean()
    S0['best_head_no_evaluator'] = dict(head=names[b], T=r4(T), C=r4(C), ioi=r4((1 - T) + max(0, C - T)))
    g = np.random.default_rng(606)
    idx = g.integers(0, len(cols), (2000, len(cols)))
    for f in (0.25, 0.5, 0.75, 1.0):
        for k in (5, 10, 20, 50):
            S, corr, rng_id = A.scores(d, heads, base, nb, f, k)
            row, sel = {}, {}
            for e, M in S.items():
                cal = np.zeros_like(M, dtype=float)
                for i in range(len(heads)):
                    iso = IsotonicRegression(out_of_bounds='clip', y_min=0, y_max=1).fit(M[i][rng_id], corr[i][rng_id].astype(float))
                    cal[i] = iso.predict(M[i])
                pick = cal[:, tgt].argmax(0)
                t, c = corr[pick, cols].astype(float), cal[pick, cols]
                sel[e] = (t, c)
                Tm, Cm = t.mean(), c.mean()
                row[e] = dict(T=r4(Tm), C=r4(Cm), ioi=r4((1 - Tm) + max(0, Cm - Tm)), dec=r4(max(0, Cm - Tm)),
                              auroc_ood=[r4(A.auroc(M[i][tgt], corr[i][tgt])) for i in range(len(heads))],
                              auroc_id=[r4(A.auroc(M[i][rid], corr[i][rid])) for i in range(len(heads))])

            def ioi_b(e):
                t, c = sel[e]
                Tb, Cb = t[idx].mean(1), c[idx].mean(1)
                return (1 - Tb) + np.maximum(0, Cb - Tb)
            base_b = {e: ioi_b(e) for e in sel}
            for other in ('AGREE', 'CONF', 'GEO0', 'INPUT'):
                if other in base_b:
                    dd = base_b['GEO'] - base_b[other]
                    row[f'GEO-{other}'] = [r4(np.percentile(dd, q)) for q in (2.5, 50, 97.5)]
            S0['grid'][f'f{f}_k{k}'] = row
    txt = json.dumps(S0, ensure_ascii=False, separators=(',', ':'))
    open(dst, 'w', encoding='utf-8').write(txt)
    print('сводка:', dst, len(txt), 'символов')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
