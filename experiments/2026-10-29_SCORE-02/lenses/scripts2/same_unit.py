#!/usr/bin/env python3
"""LENSES-2, пост-хок на пилоте (не в зачёт): контроль «та же единица». Для k = 0…4 — суждение вызова k о каждом кандидате, у которого есть
суждение согласия и у вызова k p ≠ 0,5; уверенность огрублена той же картой, что single_c (score02_lib.coarse_map этапа); AUC по кандидатам;
среднее по k. Сравнение с pooled single_c и с agree на тех же кандидатах. Бутстреп задач (B = 4000) для agree − (среднее по k).
  python3 same_unit.py <папка опыта>"""
import json
import os
import sys

import numpy as np

X = sys.argv[1]
sys.path.insert(0, X)
import score02 as S  # noqa: E402
import score02_lib as L  # noqa: E402


def auc(c, o):
    c, o = np.asarray(c, float), np.asarray(o, bool)
    p, n = c[o], c[~o]
    if len(p) == 0 or len(n) == 0:
        return np.nan
    return float(((p[:, None] > n[None, :]).sum() + 0.5 * (p[:, None] == n[None, :]).sum()) / (len(p) * len(n)))


lab = S.labels_for('pilot')
for st in ('pilot_opus', 'pilot_haiku'):
    E = json.load(open(os.path.join(X, 'evals', f'{st}.json'), encoding='utf-8'))
    J = L.load(st)
    tasks = sorted(J)
    cmap, _ = L.coarse_map(J, tasks)
    # по задачам: для каждого кандидата с суждением agree — (уровень agree, верно agree, [(огрублённая уверенность вызова k, верно), …])
    per = {}
    for t in tasks:
        rows = {int(j.split('|')[2]): r['p'] for j, r in E['rows'].items() if r['task'] == t and r['valid']}
        items = []
        for i in range(8):
            y = i in lab[t]
            up = sum(1 for p in rows.values() if p[i] > 0.5); dn = sum(1 for p in rows.values() if p[i] < 0.5)
            if up == dn:
                continue
            ag = (round(max(up, dn) / (up + dn), 9), (up > dn) == y)
            calls = {k: (cmap[round(max(p[i], 1 - p[i]), 9)], (p[i] > 0.5) == y) for k, p in rows.items() if p[i] != 0.5}
            items.append((ag, calls))
        per[t] = items

    def stat(ts):
        A = [it[0] for t in ts for it in per[t]]
        a = auc([x for x, _ in A], [o for _, o in A])
        ks = []
        for k in range(5):
            C = [it[1][k] for t in ts for it in per[t] if k in it[1]]
            ks.append(auc([x for x, _ in C], [o for _, o in C]))
        return a, float(np.nanmean(ks))

    a, s1 = stat(tasks)
    rng = np.random.default_rng(11)
    bs = []
    for _ in range(4000):
        ts = [tasks[i] for i in rng.integers(0, len(tasks), len(tasks))]
        x, y = stat(ts)
        bs.append(x - y)
    lo, hi = np.nanquantile(bs, [0.025, 0.975])
    M = L.measures(J, tasks)
    print(f"{st}: AUC agree {a:.4f}; один вызов на кандидата, огрублённый (среднее по k) {s1:.4f}; pooled single_c {M['single_c']['auc2']:.4f}; "
          f"agree − (по одному вызову) {a - s1:+.4f} [{lo:+.4f}; {hi:+.4f}]; agree − pooled single_c {M['agree']['auc2'] - M['single_c']['auc2']:+.4f}")
