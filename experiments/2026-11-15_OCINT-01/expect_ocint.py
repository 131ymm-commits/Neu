#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCINT-01: ожидание E8 («годных способов нет») счётом на пилотных повторах (совет 62, п. 6). python3 expect_ocint.py
Числа пилота — gha_out/ocint_pilot/pilot_worlds.json (покрытие при номинале 0,90: в одной среде x из 100, для среднего
по мирам x из 10). Истинное покрытие каждого способа и статистики берётся из апостериорного распределения Beta(x + ½, n − x + ½)
(Джеффрис), затем разыгрываются счёты теста (10 · N_EXP опытов в одной среде, N_EXP для среднего; N_EXP — аргумент, по умолчанию 100) и применяется правило выбора.
Два варианта связи покрытий для среднего по мирам между способами M4–M7: независимые и общие для статистики (одни и те же
60 опытов; в пилоте эти доли у M4–M7 совпали у каждой статистики). Ширины — пилотные. Результат — в консоль и в json."""
import json
import os

import numpy as np

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
w = json.load(open(os.path.join(ROOT, 'gha_out', 'ocint_pilot', 'pilot_worlds.json'), encoding='utf-8'))
c = w['coverage']['0.9']
M = w['methods'][3:]
S = w['stats']
import sys  # noqa: E402
N_EXP = int(sys.argv[1]) if len(sys.argv) > 1 else 100     # опытов на мир в тесте
N1, N2, R = 10 * N_EXP, N_EXP, 20000
g = np.random.default_rng(7_780_000)
width = {m: float(np.mean([c['one_env'][m][s]['width_in_sd'] for s in S])) for m in M}
order = sorted(M, key=lambda m: width[m])


def run(shared):
    out = {'нет годных': 0, **{m: 0 for m in M}}
    for _ in range(R):
        elig = []
        x2s = {}
        if shared:                                       # одна доля для среднего по мирам на статистику — общая для M4–M7
            for s in S:
                k = c['mean_of_worlds'][M[0]][s]['covered']
                x2s[s] = g.binomial(N2, g.beta(k + 0.5, 10 - k + 0.5))
        for m in M:
            ok = True
            for s in S:
                k1 = c['one_env'][m][s]['covered']
                x1 = g.binomial(N1, g.beta(k1 + 0.5, 100 - k1 + 0.5))
                if shared:
                    x2 = x2s[s]
                else:
                    k2 = c['mean_of_worlds'][m][s]['covered']
                    x2 = g.binomial(N2, g.beta(k2 + 0.5, 10 - k2 + 0.5))
                ok &= (x1 / N1 >= 0.88) and (x2 / N2 >= 0.85)
            if ok:
                elig.append(m)
        if not elig:
            out['нет годных'] += 1
        else:
            pick = [m for m in order if m in elig][0]
            if M[-1] in elig and width[M[-1]] <= width[pick] + 1e-12:
                pick = M[-1]
            out[pick] += 1
    return {k: v / R for k, v in out.items()}


res = dict(source='gha_out/ocint_pilot/pilot_worlds.json', n_exp=N_EXP, draws=R, width_pilot=width, independent=run(False), shared=run(True),
           note='вероятности исходов правила выбора при размерах теста; E8 — вариант «общие» (доли для среднего по мирам у M4–M7 совпадали в пилоте)')
json.dump(res, open(os.path.join(X, f'expect_ocint_{N_EXP}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
