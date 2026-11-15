#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCREP-01: оценщики и общий счёт (пилот и тест). Все определения — из зарегистрированного кода, без изменений:
  AGREE, NB-AGREE, LR-AGREE, NB-IND, FAM-AGREE, CONF — OCCOR-01 (analyze_occor);
  VETO, MIX-LR — OCMIX-01 (analyze_ocmix).
Здесь — только сборка оценок нужного набора (чтобы в бутстрепе не считать лишнего) и счёт через analyze_occor.crowd_ioi
по готовым оценкам S (калибровка, выбор, ИОИ, верхушка top10_sel / top10_all — как в OCCOR-01 и OCMIX-01)."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), '2026-11-14_OCMIX-01'))
import analyze_ocmix as M  # noqa: E402

Z = M.Z
EVALS = ('AGREE', 'NB-AGREE', 'LR-AGREE', 'NB-IND', 'FAM-AGREE', 'CONF', 'VETO', 'MIX-LR')
label, family, load, arrays, agree_matrix, bc_ci, supported = M.label, M.family, M.load, M.arrays, M.agree_matrix, M.bc_ci, M.supported


def scores(ag, corr, logp, heads_idx, fit, fam, evals=EVALS):
    S = {}
    if 'AGREE' in evals:
        S['AGREE'] = Z.agree_scores(ag, heads_idx)
    if 'NB-AGREE' in evals:
        S['NB-AGREE'] = Z.nb_scores(ag, corr, heads_idx, fit)
    if 'LR-AGREE' in evals:
        S['LR-AGREE'] = Z.lr_scores(ag, corr, heads_idx, fit)
    if 'NB-IND' in evals:
        S['NB-IND'] = Z.nb_ind_scores(ag, corr, heads_idx, fit)[0]
    if 'FAM-AGREE' in evals:
        S['FAM-AGREE'] = Z.fam_scores(ag, fam, heads_idx)
    if 'CONF' in evals:
        S['CONF'] = logp[heads_idx]
    if 'VETO' in evals:
        S['VETO'] = M.veto_scores(ag, logp, heads_idx)
    if 'MIX-LR' in evals:
        S['MIX-LR'] = M.mixlr_scores(ag, corr, logp, heads_idx, fit)
    return S


def crowd(ag, corr, logp, fam, heads_idx, fit, cols, evals=EVALS, top10=True, auroc=False, S=None):
    """Как analyze_ocmix.crowd, но с полным набором оценщиков OCCOR-01 и OCMIX-01. У LR-AGREE и MIX-LR — lr_one_class;
    у VETO — selected_supported (доля задач cols, где выбранный ответ поддержан другой головой)."""
    S = scores(ag, corr, logp, heads_idx, fit, fam, evals) if S is None else S
    r = Z.crowd_ioi(ag, corr, logp, fam, heads_idx, fit, cols, evals=evals, top10=top10, auroc=auroc, S=S)
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


def crossfit_scores(ag, corr, logp, fam, heads_idx, fit, cols):
    """Кросс-подгонка (описательно, только точка): NB-AGREE, LR-AGREE, NB-IND — analyze_occor.crossfit_scores (5 частей,
    зерно 1204); MIX-LR — analyze_ocmix.crossfit_scores (5 частей, зерно 1304); остальные — как обычно."""
    S = Z.crossfit_scores(ag, corr, logp, heads_idx, fit, cols, fam)
    S['VETO'] = M.veto_scores(ag, logp, heads_idx)
    S['MIX-LR'] = M.crossfit_scores(ag, corr, logp, heads_idx, fit, cols)['MIX-LR']
    return S
