#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCCOR-01: оценщики, выбор головы и ИОИ (общие функции пилота и теста).

Оценщики головы i на задаче j (ответы голов — из answers.json):
  AGREE    — доля других голов с тем же ответом (как analyze_ocgeo.scores в OCGEO-01).
  NB-AGREE — ровно как в разведке OCGEO-01 (explore_patterns.py, § 9): по задачам набора fit для каждой другой головы o
             p1 = P(ответ o совпал с ответом i | i верна), p0 = P(совпал | i неверна), сглаживание +1/+2;
             оценка = Σ_o [совпал ? log(p1/p0) : log((1−p1)/(1−p0))].
  LR-AGREE — логистическая регрессия по ID (L2, C = 1, закреплено до пилота): признаки — совпадения ответа головы i
             с ответом каждой другой головы (0/1), цель — правильность i; оценка — логит. В отличие от NB-AGREE учитывает
             и зависимость голосующих между собой (клоны как голосующие не считаются многократно). Добавлен до данных
             пилота: сухой прогон показал, что NB-AGREE считает голоса клонов за независимые доводы.
  NB-IND   — контроль на неспецифичность (в HYPOTHESIS — W-AGREE): та же формула при независимых ошибках:
             p1 = точность o на fit, p0 = (1 − точность o) · s̄, где s̄ — общая по всем упорядоченным парам доля одинаковых
             неверных ответов (P(совпали | обе неверны)) на fit; сглаживание +1/+2. Знает надёжность голов, но не знает,
             кто с кем ошибается одинаково.
  FAM-AGREE — контроль «группировка по имени» (как HFV в arXiv:2603.17111): у каждого другого семейства один голос —
             доля его членов с тем же ответом; своё семейство не голосует. Семейство — имя репозитория.
  CONF     — logp ответа головы (нет числа → −50).
Калибровка, выбор и ИОИ — функции зарегистрированного анализа OCGEO-01 (analyze_ocgeo_test.calibrate / select / ioi):
изотоническая регрессия по задачам fit отдельно по головам; на задаче OOD выбирается голова с наибольшей откалиброванной
вероятностью; ничья — «поровну»; ИОИ = (1 − T) + max(0, C − T)."""
import itertools
import json
import os
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression

HERE = os.path.dirname(os.path.abspath(__file__))
OCGEO = os.path.join(os.path.dirname(HERE), '2026-11-14_OCGEO-01')
sys.path.insert(0, OCGEO)
import analyze_ocgeo as A  # noqa: E402  (auroc)
import analyze_ocgeo_test as T  # noqa: E402  (calibrate, select, ioi)

EVALS = ('AGREE', 'NB-AGREE', 'LR-AGREE', 'NB-IND', 'FAM-AGREE', 'CONF')
LR_C = 1.0
CONF_NONE = -50.0


def label(h):
    return h['model'] if h['revision'] == 'main' else f"{h['model']}@{h['revision']}"


def family(h):
    return h['model']


def load(out_dir):
    d = json.load(open(os.path.join(out_dir, 'answers.json'), encoding='utf-8'))
    heads = [h for h in d['heads'] if 'rows' in h]
    return d, heads


def arrays(d, heads):
    """ans — список списков (None — нет числа); corr — (головы, задачи) bool; rid — ID-маска; logp — (головы, задачи)."""
    ans = [[r['answer'] for r in h['rows']] for h in heads]
    corr = np.array([[bool(r['correct']) for r in h['rows']] for h in heads])
    rid = np.array([p['range'] == 'ID' for p in d['problems']])
    logp = np.array([[r['logp'] if r['logp'] is not None else CONF_NONE for r in h['rows']] for h in heads], float)
    return ans, corr, rid, logp


def agree_matrix(ans):
    """ag[i, o, j] — ответ o совпал с ответом i на задаче j (None не совпадает ни с чем)."""
    nh, n = len(ans), len(ans[0])
    A_ = np.array([[-1 if x is None else x for x in a] for a in ans])
    ag = (A_[:, None, :] == A_[None, :, :]) & (A_[:, None, :] >= 0)
    for i in range(nh):
        ag[i, i] = False
    return ag


def agree_scores(ag, heads_idx):
    out = []
    for i in heads_idx:
        others = [o for o in heads_idx if o != i]
        out.append(ag[i][others].mean(0))
    return np.array(out)


def nb_scores(ag, corr, heads_idx, fit):
    """NB-AGREE по головам heads_idx; параметры — по задачам fit (индексы, возможно с повторами)."""
    out = []
    for i in heads_idx:
        c = corr[i][fit]
        s = np.zeros(ag.shape[2])
        for o in heads_idx:
            if o == i:
                continue
            g = ag[i, o][fit]
            p1 = (g[c].sum() + 1) / (c.sum() + 2)
            p0 = (g[~c].sum() + 1) / ((~c).sum() + 2)
            s += np.where(ag[i, o], np.log(p1 / p0), np.log((1 - p1) / (1 - p0)))
        out.append(s)
    return np.array(out)


def nb_ind_scores(ag, corr, heads_idx, fit):
    """NB-IND: независимые ошибки — точности голов и одна общая доля одинаковых неверных ответов s̄ на fit."""
    same = both = 0
    for i, o in itertools.permutations(heads_idx, 2):
        w = ~corr[i][fit] & ~corr[o][fit]
        both += int(w.sum())
        same += int(ag[i, o][fit][w].sum())
    sbar = (same + 1) / (both + 2)
    acc = {o: (corr[o][fit].sum() + 1) / (len(fit) + 2) for o in heads_idx}
    out = []
    for i in heads_idx:
        s = np.zeros(ag.shape[2])
        for o in heads_idx:
            if o == i:
                continue
            p1, p0 = acc[o], (1 - acc[o]) * sbar
            s += np.where(ag[i, o], np.log(p1 / p0), np.log((1 - p1) / (1 - p0)))
        out.append(s)
    return np.array(out), float(sbar)


def lr_scores(ag, corr, heads_idx, fit):
    """LR-AGREE: логистическая регрессия по задачам fit; при одном классе в fit — нули (калибровка даст константу)."""
    out = []
    for i in heads_idx:
        others = [o for o in heads_idx if o != i]
        X = ag[i][others].T.astype(float)
        y = corr[i][fit]
        if y.all() or (~y).all():
            out.append(np.zeros(ag.shape[2]))
            continue
        m = LogisticRegression(C=LR_C, max_iter=2000).fit(X[fit], y)
        out.append(m.decision_function(X))
    return np.array(out)


def fam_scores(ag, fam, heads_idx):
    """FAM-AGREE (как HFV в 2603.17111, группировка по имени): у каждого другого семейства один голос — доля его членов
    с тем же ответом; своё семейство не голосует; оценка — среднее по другим семействам. Семейство — имя репозитория
    (чекпойнты одной модели — одно семейство)."""
    out = []
    for i in heads_idx:
        fams = {}
        for o in heads_idx:
            if fam[o] != fam[i]:
                fams.setdefault(fam[o], []).append(o)
        if not fams:
            out.append(np.zeros(ag.shape[2]))
            continue
        out.append(np.mean([ag[i][m].mean(0) for m in fams.values()], 0))
    return np.array(out)


def scores(ag, corr, logp, heads_idx, fit, fam=None):
    S = {'AGREE': agree_scores(ag, heads_idx), 'NB-AGREE': nb_scores(ag, corr, heads_idx, fit),
         'LR-AGREE': lr_scores(ag, corr, heads_idx, fit),
         'NB-IND': nb_ind_scores(ag, corr, heads_idx, fit)[0], 'CONF': logp[heads_idx]}
    if fam is not None:
        S['FAM-AGREE'] = fam_scores(ag, fam, heads_idx)
    return S


def crowd_ioi(ag, corr, logp, fam, heads_idx, fit, cols, evals=EVALS, top10=False):
    """ИОИ оценщиков для толпы heads_idx: калибровка по fit, выбор и мера по cols."""
    S = scores(ag, corr, logp, heads_idx, fit, fam)
    cs = corr[heads_idx]
    out = {}
    for e in evals:
        cal = T.calibrate(S[e], cs, fit, cols)
        t, c, tie = T.select(cal, cs[:, cols].astype(float))
        r = T.ioi(t, c)
        r['tie_frac'] = tie
        if top10:
            fp, fy = cal.ravel(), cs[:, cols].astype(float).ravel()
            sel = np.argsort(-fp, kind='mergesort')[:int(np.ceil(0.1 * len(fp)))]
            r['top10'] = dict(n=len(sel), accuracy=float(fy[sel].mean()), claim=float(fp[sel].mean()),
                              deception=float(fp[sel].mean() - fy[sel].mean()))
            r['auroc_ood'] = [A.auroc(S[e][k][cols], cs[k][cols]) for k in range(len(heads_idx))]
        out[e] = r
    return out


def same_wrong_rates(ans, corr, idx, heads_idx):
    """Доля одинаковых неверных ответов у пары (где обе неверны) на задачах idx; ключ — (a, b)."""
    out = {}
    for a, b in itertools.combinations(heads_idx, 2):
        both = [j for j in idx if not corr[a][j] and not corr[b][j]]
        out[(a, b)] = (float(np.mean([ans[a][j] is not None and ans[a][j] == ans[b][j] for j in both])) if both else None, len(both))
    return out
