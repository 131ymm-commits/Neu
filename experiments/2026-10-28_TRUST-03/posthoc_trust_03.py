#!/usr/bin/env python3
"""TRUST-03, пост-хок (после проверки отчёта; вердиктов не меняет, не в зачёт): разброс мгновенного u по снимкам окна
(поколения 1000–2999) и доля снимков в трети разрыва от своей точки (0 — у дальновидных рук, 1 — у близорукой);
число зёрен, где среднее по окну u в шестой части разрыва. Из results_trust_03.json → posthoc_trust_03.json.
Запуск из папки опыта: python3 posthoc_trust_03.py"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
W_FAR, D = 0.6891, 0.9873 - 0.6891
d = json.load(open(os.path.join(HERE, 'results_trust_03.json')))
G, WIN = d['params']['G'], d['params']['WINDOW']
TARGET = {'MYOPIC': 1.0, 'DEMES_NOSEL': 1.0, 'DEMES': None, 'DEMES_10x40': None, 'COUNCIL': 0.0, 'COUNCIL_10x40': 0.0,
          'DEMES_POOLED': 0.0, 'COUNCIL_IND': 0.0, 'DEMES_IND': None}
out = {}
for arm, tgt in TARGET.items():
    sds, shares, n6 = [], [], 0
    for r in d['runs']:
        if r['arm'] != arm:
            continue
        u = np.array([(t['wG'] - W_FAR) / D for t in r['traj'] if t['g'] >= G - WIN])
        sds.append(float(u.std()))
        if tgt is not None:
            shares.append(float(np.mean(np.abs(u - tgt) <= 1 / 3)))
            n6 += abs((r['final']['wG'] - W_FAR) / D - tgt) <= 1 / 6
    out[arm] = dict(sd_snap_u_mean=round(float(np.mean(sds)), 3), sd_snap_u_min=round(float(np.min(sds)), 3),
                    sd_snap_u_max=round(float(np.max(sds)), 3))
    if tgt is not None:
        out[arm].update(share_snap_within_third=round(float(np.mean(shares)), 3), n_seeds_window_mean_within_sixth=int(n6))
json.dump(out, open(os.path.join(HERE, 'posthoc_trust_03.json'), 'w'), ensure_ascii=False, indent=1)
for k, v in out.items():
    print(k.ljust(14), v)
