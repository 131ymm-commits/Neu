#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCMIX-01: оценщики-смеси и общий счёт (пилот и тест). Определения закреплены в HYPOTHESIS.md до пилота.
  AGREE, LR-AGREE, CONF — из зарегистрированного кода OCCOR-01 (analyze_occor), без изменений.
  VETO   — оценка головы i на задаче j: logp её ответа (как CONF), если этот ответ дала хотя бы ещё одна голова толпы;
           иначе logp − 1000 (неподдержанный ответ ниже любого поддержанного). Ответ без числа не поддержан никогда
           (analyze_occor.agree_matrix: None ни с чем не совпадает); его logp — −50, как у CONF.
  MIX-LR — логистическая регрессия по задачам fit на голову (L2, C = 1, как LR-AGREE): признаки — совпадения ответа головы
           с каждой другой головой и logp ответа, стандартизованный по задачам fit (среднее и разброс — по fit). Если у
           головы в fit один класс, её оценка — константа (калибровка даёт долю верных), как у LR-AGREE.
Калибровка (изотоническая по fit, по головам), выбор (наибольшая откалиброванная вероятность, ничья «поровну»), ИОИ и
верхушка (top10_sel — выбранные ответы, top10_all — все пары; граничный блок ничьих дробно) — analyze_occor.crowd_ioi
(функции OCGEO-01 и OCCOR-01) по готовым оценкам S."""
import os
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression

HERE = os.path.dirname(os.path.abspath(__file__))
OCCOR = os.path.join(os.path.dirname(HERE), '2026-11-14_OCCOR-01')
sys.path.insert(0, OCCOR)
import analyze_occor as Z  # noqa: E402

EVALS = ('AGREE', 'LR-AGREE', 'CONF', 'VETO', 'MIX-LR')
VETO_SHIFT = 1000.0
label, family, load, arrays, agree_matrix, bc_ci, top_frac = Z.label, Z.family, Z.load, Z.arrays, Z.agree_matrix, Z.bc_ci, Z.top_frac


def supported(ag, heads_idx):
    """sup[k, j] — ответ головы heads_idx[k] на задаче j дала хотя бы ещё одна голова толпы."""
    return np.array([ag[i][[o for o in heads_idx if o != i]].any(0) for i in heads_idx])


def veto_scores(ag, logp, heads_idx):
    sup = supported(ag, heads_idx)
    return np.where(sup, logp[heads_idx], logp[heads_idx] - VETO_SHIFT)


def mixlr_scores(ag, corr, logp, heads_idx, fit):
    out = []
    for i in heads_idx:
        others = [o for o in heads_idx if o != i]
        y = corr[i][fit]
        if y.all() or (~y).all():
            out.append(np.zeros(ag.shape[2]))
            continue
        lp = logp[i]
        mu, sd = float(lp[fit].mean()), float(lp[fit].std())
        X = np.column_stack([ag[i][others].T.astype(float), (lp - mu) / (sd if sd > 0 else 1.0)])
        m = LogisticRegression(C=Z.LR_C, max_iter=2000).fit(X[fit], y)
        out.append(m.decision_function(X))
    return np.array(out)


def scores(ag, corr, logp, heads_idx, fit, evals=EVALS):
    S = {}
    if 'AGREE' in evals:
        S['AGREE'] = Z.agree_scores(ag, heads_idx)
    if 'LR-AGREE' in evals:
        S['LR-AGREE'] = Z.lr_scores(ag, corr, heads_idx, fit)
    if 'CONF' in evals:
        S['CONF'] = logp[heads_idx]
    if 'VETO' in evals:
        S['VETO'] = veto_scores(ag, logp, heads_idx)
    if 'MIX-LR' in evals:
        S['MIX-LR'] = mixlr_scores(ag, corr, logp, heads_idx, fit)
    return S


def crowd(ag, corr, logp, heads_idx, fit, cols, evals=EVALS, top10=True, auroc=False):
    """ИОИ и верхушка оценщиков для толпы heads_idx: калибровка по fit, выбор и мера по cols (код OCCOR-01 по готовым S).
    У VETO — selected_supported: доля задач cols, где выбранный ответ поддержан другой головой (при ничьей — доля среди
    равных). У LR-AGREE и MIX-LR — lr_one_class (число голов с одним классом в fit)."""
    S = scores(ag, corr, logp, heads_idx, fit, evals)
    r = Z.crowd_ioi(ag, corr, logp, None, heads_idx, fit, cols, evals=evals, top10=top10, auroc=auroc, S=S)
    n1 = int(sum(1 for i in heads_idx if corr[i][fit].all() or (~corr[i][fit]).all()))
    for e in ('LR-AGREE', 'MIX-LR'):
        if e in r:
            r[e]['lr_one_class'] = n1
    if 'VETO' in r:
        cal = Z.T.calibrate(S['VETO'], corr[heads_idx], fit, cols)
        tied = np.abs(cal - cal.max(0)[None, :]) <= 1e-12
        sup = supported(ag, heads_idx)[:, cols]
        r['VETO']['selected_supported'] = float(np.mean((sup & tied).sum(0) / tied.sum(0)))
    return r
