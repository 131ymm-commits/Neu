#!/usr/bin/env python3
"""LENSES-2: порождающая модель для нуля X1oc (согласие ранжирует так же, как огрублённый вызов). Импорт ничего не пишет.
Кандидат i задачи t: метка z_i (4 из 8 — «в лучшей половине»). Ясность: с вероятностью pi кандидат ясный (вызов следует мнению с
вероятностью chi), иначе неясный (clo). Мнение b_i = z_i с вероятностью a_hi у ясного и a_lo у неясного, плюс сдвиг задачи tau·N(0,1)
(разная трудность задач; обрезано в [0,05; 0,95]).
Вызов k: с вероятностью p05 — p = 0,5; иначе сторона = мнение (с вероятностью ясности) или обратная; модуль
m = 0,05 + msc·σ(s·(±1: сторона вызова верна / нет) + kap·(±1: кандидат ясный / нет) + N(0, 1)); p = 0,5 ± m, округление как у голов
(к 0,05 с вероятностью g05, иначе к 0,01).
s — насколько словесная уверенность знает правоту своего вызова сверх ясности (s = 0 — не знает); kap — насколько она знает ясность
(ту же величину, что и согласие). Суждения — score02.judgments (семантика опыта)."""
import os
import sys

import numpy as np

X = os.environ.get('SCORE02_COPY')
if X:
    sys.path.insert(0, X)

sig = lambda x: 1 / (1 + np.exp(-x))


def gen_task(rng, P, K=5):
    shift = P['tau'] * rng.standard_normal()
    z = np.array([1] * 4 + [-1] * 4)
    clear = rng.random(8) < P['pi']
    at = np.clip(np.where(clear, P['a_hi'], P['a_lo']) + shift, 0.05, 0.95)
    b = np.where(rng.random(8) < at, z, -z)
    ci = np.where(clear, P['chi'], P['clo'])
    rows = {}
    for k in range(K):
        follow = rng.random(8) < ci
        side = np.where(follow, b, -b)
        corr = side == z
        m = 0.05 + P['msc'] * sig(P['s'] * np.where(corr, 1.0, -1.0) + P['kap'] * np.where(clear, 1.0, -1.0) + rng.standard_normal(8))
        p = 0.5 + side * m
        g = rng.random(8) < P['g05']
        p = np.where(g, np.round(p * 20) / 20, np.round(p, 2))
        p = np.where(rng.random(8) < P['p05'], 0.5, p)
        p = np.clip(p, 0.01, 0.99)
        rows[k] = [float(round(x, 2)) for x in p]
    return rows


def gen_stage(rng, P, n, K=5):
    import score02 as S
    lab = {0, 1, 2, 3}
    return {f'T{t:05d}': S.judgments(gen_task(rng, P, K), lab, K) for t in range(n)}


OPUS = dict(a_hi=0.66, a_lo=0.52, tau=0.15, pi=0.5, chi=0.995, clo=0.78, s=0.0, kap=0.8, msc=0.35, p05=0.054, g05=0.75)
HAIKU = dict(a_hi=0.62, a_lo=0.52, tau=0.15, pi=0.3, chi=0.99, clo=0.75, s=0.0, kap=0.8, msc=0.33, p05=0.089, g05=0.75)
