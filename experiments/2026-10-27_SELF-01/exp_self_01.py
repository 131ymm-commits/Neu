#!/usr/bin/env python3
"""EXP-SELF-01 — «Кого оставит горлышко: себя или другого?»

Запуск:  OMP_NUM_THREADS=1 python3 exp_self_01.py   (несколько минут на 2 ядрах CPU)
Результаты: exp_self_01_results.json и сводка в stdout. Предрегистрация: EXP-SELF-01_PREREG.md
"""
import json
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

NAMES = ["SELF", "TOOL", "OTHER", "OTHER_TOOL", "OBJECT"]
COUPLE = np.array([1.0, 0.75, 1.0, 0.75, 0.0])  # связь с ведущим действием
RHO = 0.8                                       # инерция
N_TR, N_TE = 12_000, 4_000
KS = [1, 2, 3, 4, 6, 8, 16]
QS = [0.0, 0.5, 1.0]                             # доля шагов, где модель видит своё действие


def simulate(seed, q):
    """SELF и TOOL ведёт моё действие a; OTHER и OTHER_TOOL — скрытое действие b другого агента."""
    rng = np.random.default_rng(seed)
    T, burn = N_TR + N_TE, 200
    n = T + burn + 1
    a = rng.standard_normal((n, 2))
    b = rng.standard_normal((n, 2))
    eta = rng.standard_normal((n, 5, 2))
    drive = np.zeros((n, 5, 2))
    drive[:, 0] = a
    drive[:, 1] = a
    drive[:, 2] = b
    drive[:, 3] = b
    inc = COUPLE[None, :, None] * drive + np.sqrt(1 - COUPLE ** 2)[None, :, None] * eta
    x = np.zeros((n, 5, 2))
    x[1:] = lfilter([1.0], [1.0, -RHO], inc[:-1], axis=0)       # x_{t+1} = RHO*x_t + inc_t
    m = (np.random.default_rng(seed + 10_000).random(n) < q).astype(float)  # вложенные маски
    x0, x1 = x[burn:burn + T], x[burn + 1:burn + T + 1]
    a0, m0 = a[burn:burn + T], m[burn:burn + T, None]
    X = np.concatenate([x0.reshape(T, 10), a0 * m0, m0], axis=1)
    Y = x1.reshape(T, 10)
    P = RHO * x0                                 # предсказуемая часть x_{t+1} при данном входе
    P[:, 0] += COUPLE[0] * a0 * m0
    P[:, 1] += COUPLE[1] * a0 * m0
    return X, Y, P.reshape(T, 10)


def prep(seed, q):
    X, Y, P = simulate(seed, q)
    sx, sy = StandardScaler().fit(X[:N_TR]), StandardScaler().fit(Y[:N_TR])
    X, Y, P = sx.transform(X), sy.transform(Y), sy.transform(P)
    return X[:N_TR], X[N_TR:], Y[:N_TR], Y[N_TR:], P[:N_TR], P[N_TR:]


def probe(Ztr, Zte, Ptr, Pte):
    """R² линейного зонда из представления в предсказуемое следующее состояние каждого объекта."""
    out = []
    for i in range(5):
        s = slice(2 * i, 2 * i + 2)
        r = Ridge(alpha=1e-3).fit(Ztr, Ptr[:, s])
        out.append(float(r2_score(Pte[:, s], r.predict(Zte), multioutput="variance_weighted")))
    return out


def ols(Xtr, Ytr):
    A = np.c_[Xtr, np.ones(len(Xtr))]
    return np.linalg.lstsq(A, Ytr, rcond=None)[0]


def rrr_codes(Xtr, Xte, Ytr, k):
    """Линейная теория: оптимальное горлышко ранга k (reduced-rank regression)."""
    W = ols(Xtr, Ytr)
    Ftr = np.c_[Xtr, np.ones(len(Xtr))] @ W
    Fte = np.c_[Xte, np.ones(len(Xte))] @ W
    U = np.linalg.eigh(np.cov(Ftr.T))[1][:, ::-1][:, :min(k, 10)]
    return Ftr @ U, Fte @ U


def bottleneck(mlp, X):
    h = np.tanh(X @ mlp.coefs_[0] + mlp.intercepts_[0])
    return np.tanh(h @ mlp.coefs_[1] + mlp.intercepts_[1])


def fit_one(q, k, seed):
    warnings.filterwarnings("ignore", category=ConvergenceWarning)
    Xtr, Xte, Ytr, Yte, Ptr, Pte = prep(seed, q)
    mlp = MLPRegressor(hidden_layer_sizes=(64, k, 64), activation="tanh", solver="adam",
                       learning_rate_init=1e-3, batch_size=200, max_iter=60, tol=1e-6,
                       n_iter_no_change=10, random_state=seed).fit(Xtr, Ytr)
    Rtr, Rte = rrr_codes(Xtr, Xte, Ytr, k)
    return dict(q=q, k=k, seed=seed,
                mlp=probe(bottleneck(mlp, Xtr), bottleneck(mlp, Xte), Ptr, Pte),
                rrr=probe(Rtr, Rte, Ptr, Pte),
                fit=float(r2_score(Pte, mlp.predict(Xte), multioutput="variance_weighted")),
                epochs=int(mlp.n_iter_))


def learning_curve(q, seed, k=16, epochs=5, chunk=400):
    """H4: что выучивается раньше (SGD, горлышко не давит)."""
    warnings.filterwarnings("ignore", category=ConvergenceWarning)
    Xtr, Xte, Ytr, Yte, Ptr, Pte = prep(seed, q)
    mlp = MLPRegressor(hidden_layer_sizes=(64, k, 64), activation="tanh", solver="sgd",
                       learning_rate_init=0.01, momentum=0.9, batch_size=200, random_state=seed)
    rng, cur = np.random.default_rng(seed), []
    for _ in range(epochs):
        idx = rng.permutation(N_TR)
        for c in range(0, N_TR, chunk):
            j = idx[c:c + chunk]
            mlp.partial_fit(Xtr[j], Ytr[j])
            pr = mlp.predict(Xte)
            cur.append([float(r2_score(Pte[:, 2 * i:2 * i + 2], pr[:, 2 * i:2 * i + 2],
                                       multioutput="variance_weighted")) for i in range(5)])
    cur = np.array(cur)
    fin = cur[-1]
    t80 = [int(np.argmax(cur[:, i] >= 0.8 * fin[i])) if fin[i] > 0.2 else -1 for i in range(5)]
    return dict(q=q, seed=seed, final=fin.round(3).tolist(), t80=t80, curve=cur.round(4).tolist())


def spectrum(q, seed=0):
    """Собственные числа ковариации предсказуемой части (x-координаты) и λ₂/λ₁."""
    Xtr, _, Ytr, _, _, _ = prep(seed, q)
    F = np.c_[Xtr, np.ones(len(Xtr))] @ ols(Xtr, Ytr)
    ev = np.sort(np.linalg.eigvalsh(np.cov(F[:, 0::2].T)))[::-1]
    return dict(eig=ev.round(3).tolist(), gap=round(float(ev[1] / ev[0]), 3))


if __name__ == "__main__":
    t0 = time.time()
    jobs = [(q, 2, s) for q in QS for s in range(10)]
    jobs += [(q, k, s) for q in QS for k in KS if k != 2 for s in range(3)]
    fits = Parallel(n_jobs=2)(delayed(fit_one)(*j) for j in jobs)
    curves = Parallel(n_jobs=2)(delayed(learning_curve)(q, s) for q in (1.0, 0.0) for s in range(3))
    spec = {str(q): spectrum(q) for q in QS}
    with open("exp_self_01_results.json", "w") as f:
        json.dump(dict(names=NAMES, fits=fits, curves=curves, spectrum=spec), f)

    def sel(q, k):
        return [r for r in fits if r["q"] == q and r["k"] == k]

    print("λ₂/λ₁:", {q: spec[str(q)]["gap"] for q in QS},
          "| старшие собств. числа:", {q: spec[str(q)]["eig"][:3] for q in QS})
    for q in QS:
        print(f"\nq={q}: R² зонда MLP|линейная теория —", "  ".join(NAMES))
        for k in KS:
            rows = sel(q, k)
            m = np.mean([x["mlp"] for x in rows], 0)
            r = np.mean([x["rrr"] for x in rows], 0)
            print(f" k={k:>2} n={len(rows):>2} fit={np.mean([x['fit'] for x in rows]):.2f}  "
                  + "  ".join(f"{u:.2f}|{v:.2f}" for u, v in zip(m, r)))
    wins, means = {}, {}
    for q in QS:
        rows = sel(q, 2)
        wins[q] = int(sum(x["mlp"][0] > x["mlp"][2] for x in rows))
        means[q] = np.mean([x["mlp"] for x in rows], 0)
        print(f"k=2, q={q}: SELF>OTHER в {wins[q]}/{len(rows)}; средние R² {np.round(means[q], 2).tolist()}")
    for c in curves:
        print(f"кривая q={c['q']} seed={c['seed']}: финал {c['final']}, t80 (порции по 400) {c['t80']}")
    h4 = [c for c in curves if c["q"] == 1.0]
    verdict = {
        "H1": bool(means[1.0][0] >= 0.8 and means[1.0][2] <= 0.2),
        "H2": bool(2 <= wins[0.0] <= 8 and wins[1.0] >= 9),
        "H3": bool(wins[0.5] >= 8),
        "H4": bool(all(min(c["t80"][:4]) >= 0 and c["t80"][0] < c["t80"][2] and c["t80"][1] < c["t80"][3]
                       for c in h4)),
        "E1": bool(means[1.0][1] >= 0.7 and means[1.0][3] <= 0.2),
    }
    print("\nВердикты:", verdict, f"| {time.time() - t0:.0f} с")
