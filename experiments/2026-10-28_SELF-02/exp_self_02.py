#!/usr/bin/env python3
"""SELF-02 — что выучивается первым и что переживает сжатие: «я», другой или вещь.

Часть A — повтор SELF-01 (H1–H3, E1) на новых зёрнах тем же кодом (`fit_one` импортируется из SELF-01),
         плюс проверка вне обучающего диапазона: действия ×2.
Часть B — порядок обучения при отбелённых входах: мелкая (ленивая) линейная модель, глубокая линейная
         сеть с малой и большой инициализацией, tanh-сеть с малой инициализацией; полный градиентный спуск.

Запуск: OMP_NUM_THREADS=1 python3 exp_self_02.py [--pilot]   (--pilot: зерно 999, только печать динамики)
Результаты: results_self_02.json. Предрегистрация: PREREG-SELF-02.md.
"""
import json
import os
import sys
import time
import warnings

import numpy as np
from joblib import Parallel, delayed
from scipy.signal import lfilter
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '2026-10-27_SELF-01'))
import exp_self_01 as s1  # noqa: E402  — мир, разбиение, зонд и fit_one — ровно код SELF-01

NAMES = s1.NAMES
N_TR, N_TE = s1.N_TR, s1.N_TE
QS = [0.0, 0.5, 1.0]
SEEDS_A = list(range(100, 110))      # часть A: новые зёрна (SELF-01 брал 0–9)
SEEDS_B = list(range(200, 210))      # часть B
PILOT_SEED = 999


# ---------- часть A ----------
def simulate_scaled(seed, q, scale):
    """Копия s1.simulate с множителем действий `scale` (обоих агентов). scale = 1 воспроизводит s1.simulate
    побитно (проверка — test_same_world)."""
    rng = np.random.default_rng(seed)
    T, burn = N_TR + N_TE, 200
    n = T + burn + 1
    a = rng.standard_normal((n, 2)) * scale
    b = rng.standard_normal((n, 2)) * scale
    eta = rng.standard_normal((n, 5, 2))
    drive = np.zeros((n, 5, 2))
    drive[:, 0] = a
    drive[:, 1] = a
    drive[:, 2] = b
    drive[:, 3] = b
    inc = s1.COUPLE[None, :, None] * drive + np.sqrt(1 - s1.COUPLE ** 2)[None, :, None] * eta
    x = np.zeros((n, 5, 2))
    x[1:] = lfilter([1.0], [1.0, -s1.RHO], inc[:-1], axis=0)
    m = (np.random.default_rng(seed + 10_000).random(n) < q).astype(float)
    x0, x1 = x[burn:burn + T], x[burn + 1:burn + T + 1]
    a0, m0 = a[burn:burn + T], m[burn:burn + T, None]
    X = np.concatenate([x0.reshape(T, 10), a0 * m0, m0], axis=1)
    Y = x1.reshape(T, 10)
    P = s1.RHO * x0
    P[:, 0] += s1.COUPLE[0] * a0 * m0
    P[:, 1] += s1.COUPLE[1] * a0 * m0
    return X, Y, P.reshape(T, 10)


def test_same_world():
    for q in QS:
        A, B = s1.simulate(7, q), simulate_scaled(7, q, 1.0)
        assert all(np.array_equal(u, v) for u, v in zip(A, B)), q
    return True


def fit_A(q, seed, k=2):
    """То же, что s1.fit_one (те же гиперпараметры и random_state), плюс зонд вне диапазона (действия ×2)."""
    warnings.filterwarnings("ignore", category=ConvergenceWarning)
    base = s1.fit_one(q, k, seed)                     # ровно функция SELF-01
    X, Y, P = s1.simulate(seed, q)
    sx, sy = StandardScaler().fit(X[:N_TR]), StandardScaler().fit(Y[:N_TR])
    Xtr, Ptr = sx.transform(X[:N_TR]), sy.transform(P[:N_TR])
    mlp = MLPRegressor(hidden_layer_sizes=(64, k, 64), activation="tanh", solver="adam",
                       learning_rate_init=1e-3, batch_size=200, max_iter=60, tol=1e-6,
                       n_iter_no_change=10, random_state=seed).fit(Xtr, sy.transform(Y[:N_TR]))
    Xo, Yo, Po = simulate_scaled(seed + 5000, q, 2.0)  # вне диапазона: другое зерно, действия ×2
    Xo, Po = sx.transform(Xo[N_TR:]), sy.transform(Po[N_TR:])
    ztr, zo = s1.bottleneck(mlp, Xtr), s1.bottleneck(mlp, Xo)
    ood = s1.probe(ztr, zo, Ptr, Po)                   # зонд учится в диапазоне, проверяется вне его
    same = bool(np.allclose(s1.probe(ztr, s1.bottleneck(mlp, sx.transform(X[N_TR:])), Ptr,
                                     sy.transform(P[N_TR:])), base['mlp'], atol=1e-9))
    return dict(q=q, k=k, seed=seed, mlp=base['mlp'], rrr=base['rrr'], ood=ood, same_as_s1=same)


# ---------- часть B ----------
def whiten_data(seed, q):
    """Разбиение и стандартизация как в s1.prep, затем отбеливание входа по обучающей части (PCA)."""
    Xtr, Xte, Ytr, Yte, Ptr, Pte = s1.prep(seed, q)
    C = np.cov(Xtr.T, bias=True)
    ev, V = np.linalg.eigh(C)
    keep = ev > 1e-8 * ev.max()
    Wh = V[:, keep] / np.sqrt(ev[keep])
    mu = Xtr.mean(0)
    return (Xtr - mu) @ Wh, (Xte - mu) @ Wh, Ytr, Ptr, Pte


def r2_objects(Pte, pred):
    return [float(r2_score(Pte[:, 2 * i:2 * i + 2], pred[:, 2 * i:2 * i + 2], multioutput="variance_weighted"))
            for i in range(5)]


def theory(seed, q):
    """Сила мод по кластерам (отбелённый вход; s = √λ, λ — старшее собственное число ковариации OLS-предсказания
    внутри блока). Кластеры: S = (SELF, TOOL), O = (OTHER, OTHER_TOOL), B = OBJECT; среднее по координатам x и y.
    Порядок по кластерам, а не по сортировке: при q = 0 старшим может оказаться любой из двух тел."""
    Xw, _, Ytr, _, _ = whiten_data(seed, q)
    W = Xw.T @ Ytr / len(Xw)                    # при отбелённом входе OLS = Σ_xy
    F = Xw @ W
    lam = {}
    for name, objs in (('S', (0, 1)), ('O', (2, 3)), ('B', (4,))):
        vals = []
        for c in (0, 1):                        # x и y
            cols = [2 * i + c for i in objs]
            Cb = np.atleast_2d(np.cov(F[:, cols].T))
            vals.append(float(np.linalg.eigvalsh(Cb).max()))
        lam[name] = float(np.mean(vals))
    return lam


def train_curve(seed, q, model, steps, lr, init, h=64):
    """Полный градиентный спуск на ½·MSE. model ∈ {'lin1', 'lin2', 'tanh2'}; init — σ весов (lin2/tanh2).
    Возвращает R² по объектам на тесте после каждого шага, потолок OLS (по обучающей части: R² OLS на Ptr),
    размер отбелённого входа d и — для ленивой глубокой линейной сети — кривую её линеаризации около начала
    (ядро заморожено: M ← M − lr·(G·W2₀ᵀW2₀ + W1₀W1₀ᵀ·G), G = Xᵀ(XM − Y)/n)."""
    Xw, Xte, Y, Ptr, Pte = whiten_data(seed, q)
    n, d = Xw.shape
    rng = np.random.default_rng(seed + 777)
    M_ols = Xw.T @ Y / n
    ref = r2_objects(Ptr, Xw @ M_ols)            # потолок: OLS на обучающей части
    curve = []
    if model == 'lin1':
        W = np.zeros((d, 10))
        for _ in range(steps):
            W += lr * (Xw.T @ (Y - Xw @ W) / n)
            curve.append(r2_objects(Pte, Xte @ W))
        return np.array(curve), ref, d, None
    s1_, s2_ = (init, init) if init > 0 else (1 / np.sqrt(d), 1 / np.sqrt(h))   # init ≤ 0 → «ленивая» (LeCun)
    W1 = rng.standard_normal((d, h)) * s1_
    W2 = rng.standard_normal((h, 10)) * s2_
    curve_lin = None
    if model == 'lin2' and init <= 0:                                        # линеаризация около начала
        A, B, M = W2.T @ W2, W1 @ W1.T, W1 @ W2
        curve_lin = []
        for _ in range(steps):
            G = Xw.T @ (Xw @ M - Y) / n
            M = M - lr * (G @ A + B @ G)
            curve_lin.append(r2_objects(Pte, Xte @ M))
        curve_lin = np.array(curve_lin)
    for _ in range(steps):
        Z = Xw @ W1
        H = np.tanh(Z) if model == 'tanh2' else Z
        E = H @ W2 - Y
        gW2 = H.T @ E / n
        gH = E @ W2.T
        gZ = gH * (1 - H ** 2) if model == 'tanh2' else gH
        gW1 = Xw.T @ gZ / n
        W1 -= lr * gW1
        W2 -= lr * gW2
        Ht = np.tanh(Xte @ W1) if model == 'tanh2' else Xte @ W1
        curve.append(r2_objects(Pte, Ht @ W2))
    return np.array(curve), ref, d, curve_lin


def t_half(curve, ref, frac=0.5):
    """Первый шаг (с 1), на котором R² объекта достигает frac его потолка OLS. Не достиг — цензура:
    шагов + 1 (позже любого достигнутого) и флаг в списке censored."""
    out, cens = [], []
    for i in range(5):
        hit = np.nonzero(curve[:, i] >= frac * ref[i])[0]
        out.append(int(hit[0]) + 1 if len(hit) else len(curve) + 1)
        cens.append(not len(hit))
    return out, cens


ARMS = {  # имя: (model, steps, lr, init)
    'lin1': ('lin1', 60, 0.1, 0.0),
    'lin2_small': ('lin2', 300, 0.1, 1e-3),
    'lin2_lazy': ('lin2', 600, 0.003, -1.0),
    'tanh2_small': ('tanh2', 300, 0.1, 1e-3),
}


def run_B(seed, q, arm):
    model, steps, lr, init = ARMS[arm]
    curve, ref, d, curve_lin = train_curve(seed, q, model, steps, lr, init)
    th, cens = t_half(curve, ref)
    lam = theory(seed, q)
    out = dict(seed=seed, q=q, arm=arm, d=int(d), t_half=th, censored=cens, ref=ref, final=curve[-1].tolist(), lam=lam,
               rho_theory_other=float(np.sqrt(lam['S'] / lam['O'])),
               rho_theory_object=float(np.sqrt(lam['S'] / lam['B'])),
               curve=curve.round(4).tolist())
    if curve_lin is not None:
        out['t_half_lin'], out['censored_lin'] = t_half(curve_lin, ref)
    return out


def pilot():
    assert test_same_world()
    print('test_same_world: ok')
    a = fit_A(1.0, PILOT_SEED)
    print('A (q=1, k=2):', np.round(a['mlp'], 2), 'ood', np.round(a['ood'], 2), 'same_as_s1', a['same_as_s1'])
    a4 = fit_A(1.0, PILOT_SEED, k=4)
    print('A (q=1, k=4):', np.round(a4['mlp'], 2), 'rrr', np.round(a4['rrr'], 2))
    for q in QS:
        for arm in ARMS:
            r = run_B(PILOT_SEED, q, arm)
            th = r['t_half']
            print(f"q={q} {arm:12s} d={r['d']} t½ {th} цензура {r['censored']}  ρ_OTHER {th[2] / th[0]:.3f} "
                  f"(теор. {r['rho_theory_other']:.3f})  ρ_OBJECT {th[4] / th[0]:.3f} (теор. {r['rho_theory_object']:.3f})  "
                  f"final {np.round(r['final'], 3)}" + (f"  t½ линеаризации {r['t_half_lin']}" if 't_half_lin' in r else ''))
            if arm in ('lin2_small', 'lin2_lazy') and q == 1.0:
                c = np.array(r['curve'])
                for j in list(range(0, 90, 6)) + [len(c) - 1]:
                    if j < len(c):
                        print('   шаг', j + 1, np.round(c[j], 3))


if __name__ == '__main__':
    if '--pilot' in sys.argv:
        pilot(); sys.exit(0)
    dry = '--dry' in sys.argv                     # сухой прогон цепочки: зёрна 990–991, вывод в dry/
    sa, sb = ([990, 991], [990, 991]) if dry else (SEEDS_A, SEEDS_B)
    outdir = os.path.join(HERE, 'dry') if dry else HERE
    os.makedirs(outdir, exist_ok=True)
    t0 = time.time()
    assert test_same_world()
    jobs = [(q, s, 2) for q in QS for s in sa] + [(1.0, s, 4) for s in sa]     # k = 4 — лестница потерь (R7)
    A = Parallel(n_jobs=2)(delayed(fit_A)(q, s, k) for q, s, k in jobs)
    B = Parallel(n_jobs=2)(delayed(run_B)(s, q, arm) for q in QS for arm in ARMS for s in sb)
    json.dump(dict(names=NAMES, A=A, B=B, seconds=time.time() - t0), open(os.path.join(outdir, 'results_self_02.json'), 'w'))
    print(f'готово за {time.time() - t0:.0f} с; анализ — analyze_self_02.py')
