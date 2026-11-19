#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-03: мощность решающих проверок до прогона — на заглушке с заложенным эффектом +δ на диагонали (совет 75).
Шум — взаимодействие «программа × голова» из пилотной матрицы T_X19: матрица вида (prog, shape) двойным центрированием
очищается от эффектов строк и столбцов; σ — ст. откл. её внедиагональных клеток. Две модели шума:
  «общий» — одна матрица шума на все среды семейства (усреднение по средам шум не уменьшает; осторожная);
  «независимый» — свой шум в каждой среде (среднее по n средам).
Для каждого δ — доля повторов с p ≤ α (точный перебор 7! перестановок, ab.perm_test). Пишет δ при мощности 0,8.
  python3 power_ab.py PILOT.json ВЫХОД.json [--alpha 0.0125] [--reps 400] [--seed 20261119]"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ab  # noqa: E402

N_ENVS = {'thousands': 7, 'length': 3}


def double_center(M):
    M = np.asarray(M, float)
    return M - M.mean(axis=0, keepdims=True) - M.mean(axis=1, keepdims=True) + M.mean()


def sigma_offdiag(M):
    R = double_center(M)
    k = R.shape[0]
    off = R[~np.eye(k, dtype=bool)]
    return float(np.std(off, ddof=1))


def power(sigma, delta, n_env, shared, reps, alpha, rng, k=7):
    hits = 0
    for _ in range(reps):
        if shared:
            Z = rng.normal(0, sigma, (k, k))
            mats = [Z + delta * np.eye(k)] * n_env
        else:
            mats = [rng.normal(0, sigma, (k, k)) + delta * np.eye(k) for _ in range(n_env)]
        hits += ab.perm_test(ab.s_table(mats))['p'] <= alpha
    return hits / reps


def main(a):
    pilot = json.load(open(a[0], encoding='utf-8'))
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d   # noqa: E731
    alpha, reps, seed = float(opt('--alpha', '0.0125')), int(opt('--reps', '400')), int(opt('--seed', '20261119'))
    rng = np.random.default_rng(seed)
    fam = pilot['families']['thousands']
    env = fam['envs'][ab.PILOT_ENVS[0]]
    out = dict(alpha=alpha, reps=reps, seed=seed, pilot_env=ab.PILOT_ENVS[0], kinds={})
    for kind in ab.KINDS:
        M = np.array(env[kind], float)
        sig = sigma_offdiag(M)
        D_pilot = fam[kind]['D']
        grid = sorted(set([round(x, 6) for x in np.concatenate([np.linspace(0, 4 * sig, 17), [abs(D_pilot)]])]))
        res = {}
        for fam_name, n_env in N_ENVS.items():
            for shared in (True, False):
                curve = [(d, power(sig, d, n_env, shared, reps, alpha, rng)) for d in grid]
                d80 = next((d for d, pw in curve if pw >= 0.8), None)
                res[f"{fam_name}_{'общий' if shared else 'независимый'}"] = dict(n_env=n_env, curve=curve, delta_80=d80,
                                                                                 power_at_pilot_D=dict(curve).get(round(abs(D_pilot), 6)))
        out['kinds'][kind] = dict(sigma_offdiag=sig, pilot_D=D_pilot, pilot_p=fam[kind]['p'], results=res)
        print(kind, '| σ взаимодействия', round(sig, 5), '| D пилота', round(D_pilot, 5), '| p пилота', round(fam[kind]['p'], 5))
        for k2, r in res.items():
            print('   ', k2, '| δ при мощности 0,8:', r['delta_80'], '| мощность при D пилота:', r['power_at_pilot_D'])
    json.dump(out, open(a[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
