#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-03: мощность решающих проверок до прогона — на заглушке с заложенным эффектом +δ на диагонали (совет 75).
Шум — взаимодействие «программа × голова» из пилотной матрицы T_X19: матрица вида (prog, shape) двойным центрированием
очищается от эффектов строк и столбцов; остатки — её внедиагональные клетки (42 числа), σ — их ст. откл. Модели шума:
  «норм» — клетки N(0, σ²); «эмп» — клетки берутся с возвращением из 42 остатков пилота (тяжёлые хвосты, как у OLMo);
  «общий» — одна матрица шума на все среды семейства (среднее по средам шум не уменьшает);
  «независимый» — свой шум в каждой среде (среднее по n средам).
При Z = 0 статистика D равна δ (s[b, b] = δ − 0), поэтому δ сравнима с D пилота. Для каждого δ — доля повторов с «да»
(D > 0 и точное p ≤ α, перебор 7! перестановок, ab.perm_test). Пишет δ при мощности 0,8 и мощность при δ = D пилота.
Пилот только на «тысячах» (T_X19): для «длины» берётся σ «тысяч» — перенос не проверялся.
  python3 power_ab.py PILOT.json ВЫХОД.json [--alpha ab.LEVEL] [--reps 400] [--seed 20261119]"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ab  # noqa: E402

N_ENVS = {'thousands': len(ab.TEST_ENVS['thousands']), 'length': len(ab.TEST_ENVS['length'])}
NOISE = ('норм', 'эмп')


def double_center(M):
    M = np.asarray(M, float)
    return M - M.mean(axis=0, keepdims=True) - M.mean(axis=1, keepdims=True) + M.mean()


def offdiag_resid(M):
    R = double_center(M)
    return R[~np.eye(R.shape[0], dtype=bool)]


def noise(kind, resid, sigma, rng, k):
    if kind == 'норм':
        return rng.normal(0, sigma, (k, k))
    return rng.choice(resid, size=(k, k), replace=True)


def power(resid, sigma, delta, n_env, shared, nkind, reps, alpha, rng, k=7):
    hits = 0
    for _ in range(reps):
        if shared:
            Z = noise(nkind, resid, sigma, rng, k)
            mats = [Z + delta * np.eye(k)] * n_env
        else:
            mats = [noise(nkind, resid, sigma, rng, k) + delta * np.eye(k) for _ in range(n_env)]
        r = ab.perm_test(ab.s_table(mats))
        hits += (r['D'] > 0) and (r['p'] <= alpha + 1e-15)
    return hits / reps


def main(a):
    pilot = json.load(open(a[0], encoding='utf-8'))
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d   # noqa: E731
    alpha, reps, seed = float(opt('--alpha', str(ab.LEVEL))), int(opt('--reps', '400')), int(opt('--seed', '20261119'))
    rng = np.random.default_rng(seed)
    fam = pilot['families']['thousands']
    env = fam['envs'][ab.PILOT_ENVS[0]]
    out = dict(alpha=alpha, reps=reps, seed=seed, pilot_env=ab.PILOT_ENVS[0], n_envs=N_ENVS, kinds={})
    for kind in ab.KINDS:
        M = np.array(env[kind], float)
        resid = offdiag_resid(M)
        sig = float(np.std(resid, ddof=1))
        D_pilot = float(fam[kind]['D'])
        grid = sorted(set([round(x, 6) for x in np.concatenate([np.linspace(0, 4 * sig, 17), [abs(D_pilot)]])]))
        res = {}
        for fam_name, n_env in N_ENVS.items():
            for nkind in NOISE:
                for shared in (True, False):
                    curve = [(d, power(resid, sig, d, n_env, shared, nkind, reps, alpha, rng)) for d in grid]
                    d80 = next((d for d, pw in curve if pw >= 0.8), None)
                    res[f"{fam_name}_{nkind}_{'общий' if shared else 'независимый'}"] = dict(
                        n_env=n_env, noise=nkind, shared=shared, curve=curve, delta_80=d80,
                        power_at_pilot_D=dict(curve).get(round(abs(D_pilot), 6)), power_at_0=dict(curve).get(0.0))
        # направление «общий шум даёт мощность не выше независимого» — проверка по кривым (допуск Монте-Карло 0,05)
        chk = {}
        for fam_name in N_ENVS:
            for nkind in NOISE:
                c1 = dict(res[f'{fam_name}_{nkind}_общий']['curve'])
                c2 = dict(res[f'{fam_name}_{nkind}_независимый']['curve'])
                chk[f'{fam_name}_{nkind}'] = dict(n_delta=len(c1), n_shared_above=int(sum(c1[d] > c2[d] + 0.05 for d in c1)))
        out['kinds'][kind] = dict(sigma_offdiag=sig, resid_min=float(resid.min()), resid_max=float(resid.max()), pilot_D=D_pilot,
                                  pilot_p=fam[kind]['p'], results=res, shared_le_independent=chk)
        print(kind, '| σ взаимодействия', round(sig, 5), '| остатки от', round(float(resid.min()), 4), 'до', round(float(resid.max()), 4),
              '| D пилота', round(D_pilot, 5), '| p пилота', round(fam[kind]['p'], 5), flush=True)
        for k2, r in res.items():
            print('   ', k2, '| δ при мощности 0,8:', r['delta_80'], '| мощность при D пилота:', r['power_at_pilot_D'],
                  '| при δ = 0:', r['power_at_0'], flush=True)
        print('    общий выше независимого более чем на 0,05:', chk, flush=True)
    json.dump(out, open(a[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
