#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCGEO-01, пилот 0 — первый взгляд (описательно, выбор постановки): где ошибаются головы, есть ли сигнал у соседей
в представлении (kNN-регрессия суммы по другим задачам пилота, исключая саму задачу), AUROC против уверенности."""
import json
import numpy as np

d = json.load(open('out/results.json'))
P = {p['id']: p for p in d['problems']}


def auroc(score, y):
    s, y = np.asarray(score, float), np.asarray(y, bool)
    if y.all() or (~y).all():
        return None
    r = s.argsort().argsort() + 1.0
    return float((r[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum()))


for m in d['models']:
    if 'rows' not in m:
        continue
    R = [r for r in m['rows'] if r['set'] == '2d']
    corr = np.array([r['correct'] for r in R])
    carry = np.array([(P[r['id']]['a'] % 10 + P[r['id']]['b'] % 10) >= 10 for r in R])
    big = np.array([P[r['id']]['sum'] >= 100 for r in R])
    line = f"{m['model']:12s} {m['revision']:5s} 2d: всего {corr.mean():.3f} | без переноса {corr[~carry].mean():.3f} с переносом {corr[carry].mean():.3f} | сумма<100 {corr[~big].mean():.3f} ≥100 {corr[big].mean():.3f}"
    print(line)
    if corr.mean() < 0.05:
        continue
    conf = np.array([r['logp_sum'] if r['logp_sum'] is not None else -99 for r in R])
    print('   CONF (logp ответа) AUROC', round(auroc(conf, corr), 3))
    H = np.load(f"out/hidden_{m['model']}_{m['revision']}.npz")
    ids = [r['id'] for r in d['models'][0]['rows']]
    idx2d = [i for i, r in enumerate(m['rows']) if r['set'] == '2d']
    sums = np.array([P[r['id']]['sum'] for r in R], float)
    ans = np.array([r['answer'] if r['answer'] is not None else -1 for r in R], float)
    for L in H.files:
        X = H[L].astype(np.float32)[idx2d]
        X = X - X.mean(0)
        X /= np.linalg.norm(X, axis=1, keepdims=True) + 1e-9
        S = X @ X.T
        np.fill_diagonal(S, -np.inf)
        nn = np.argsort(-S, axis=1)[:, :10]
        s_hat = sums[nn].mean(1)                     # kNN-регрессия суммы по соседям (их ответы по коду)
        geo = -np.abs(s_hat - ans)                   # согласие ответа головы с соседями
        err_knn = np.abs(s_hat - sums).mean()
        print(f"   {L:4s} GEO-регрессия AUROC {auroc(geo, corr):.3f} | ошибка kNN-суммы {err_knn:5.1f} | доля ответов = округл. kNN {np.mean(np.abs(np.round(s_hat) - sums) < 0.5):.3f}")
