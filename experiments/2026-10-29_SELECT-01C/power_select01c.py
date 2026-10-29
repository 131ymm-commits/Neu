#!/usr/bin/env python3
"""SELECT-01C: мощность критерия зачёта D_N по задачам прежних выборок SELECT-01 (main_an_wh.json, rep_an_wh.json, per_task).
Критерий (как в SELECT-01 §4 при первом шаге Холма): односторонний перестановочный p D_N − B_blind ≤ 0,025 и p D_N − A0 ≤ 0,05;
бюджет — отдельно (по пилоту). Сценарии — задачи (пары разностей D_N − B_blind и D_N − A0) пересэмплируются из: основной выборки
(эффект −0,185 к B_blind), повтора (−0,286) и обеих вместе; и два сдвига повтора (разброс повтора, D_N − B_blind сдвинута):
к среднему основной выборки (−0,185) и к −0,110 — так было бы, если бы в чистом контексте B_blind на задачах повтора вернулся
к регрету основной выборки (0,676 вместо 0,852), а D_N остался прежним. Бутстреп 2000, на каждую выборку 4000 перестановок знаков
(оценка Монте-Карло); зерно 0.
  python3 power_select01c.py   → power_select01c.json и печать"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SEL = os.path.join(HERE, '..', '2026-10-07_SELECT-01')
N, B, M, ALPHA_B, ALPHA_A = 99, 2000, 4000, 0.025, 0.05


def per_task(name):
    A = json.load(open(os.path.join(SEL, f'{name}_an_wh.json')))
    return np.array([[v['D_N'] - v['B_blind'], v['D_N'] - v['A0']] for v in A['per_task'].values()])


def pvals(d, S):
    obs = d.mean(axis=0)                       # (2,)
    pm = S @ d / d.shape[0]                    # (M, 2)
    return ((pm <= obs[None, :] + 1e-12).sum(axis=0) + 1) / (S.shape[0] + 1)


def main():
    rng = np.random.default_rng(0)
    S = rng.choice([-1.0, 1.0], size=(M, N))
    out = {}
    data = dict(main=per_task('main'), rep=per_task('rep'))
    data['both'] = np.vstack([data['main'], data['rep']])
    for name, target in (('rep_shift_main', -0.185), ('rep_shift_b_blind_main', -0.110)):
        X = data['rep'].copy(); X[:, 0] += target - X[:, 0].mean(); data[name] = X
    for k, X in data.items():
        hits = np.zeros(3)
        for _ in range(B):
            d = X[rng.integers(0, len(X), N)]
            p = pvals(d, S)
            a, b = p[0] <= ALPHA_B, p[1] <= ALPHA_A
            hits += (a, b, a and b)
        pw = hits / B
        out[k] = dict(n_source=len(X), mean_vs_B_blind=float(X[:, 0].mean()), mean_vs_A0=float(X[:, 1].mean()),
                      sd_vs_B_blind=float(X[:, 0].std(ddof=1)), power_vs_B_blind=pw[0], power_vs_A0=pw[1], power_both=pw[2])
        print(f"{k}: задач-источников {len(X)}, D_N − B_blind {X[:, 0].mean():+.3f} (SD {X[:, 0].std(ddof=1):.3f}), D_N − A0 {X[:, 1].mean():+.3f}; "
              f"мощность: против B_blind {pw[0]:.3f}, против A0 {pw[1]:.3f}, обе {pw[2]:.3f}")
    json.dump(out, open(os.path.join(HERE, 'power_select01c.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
