#!/usr/bin/env python3
"""TRUST-01 — выводит ли отбор формулу доверия, и что делает с уверенностью.

Мир: скрытое состояние W ∈ {0, 1}, P(W = 1) = π. Источники говорят ±1:
  пять независимых с надёжностью r = 0,55 … 0,92 и «пересказ» COPY: с вероятностью c повторяет источник 2 (r = 0,75),
  иначе — независимый источник той же надёжности.
Агент: z = w0 + Σ w_i·x_i, прогноз P(W = 1) = σ(z). Генотип — 7 весов. 400 особей, 40 эпизодов за жизнь,
мутация N(0, σ_mut) на каждый вес у каждого потомка, 1500 поколений.
Руки (чем платит отбор и как):
  KELLY   — приспособленность F = Π_e P_e(истины), эпизоды общие для всей популяции (общий риск), отбор
            Райта–Фишера ∝ F: долгосрочный рост = exp(E log F) — ставки Келли / бет-хеджинг;
  INDEP   — та же F, но у каждой особи свои эпизоды (независимый риск): отбор ∝ F максимизирует E F (арифметика);
  ACC     — F = exp(число верных решений z > 0), эпизоды общие: платят только за выбор, уверенность не оценивается;
  CONTEST — усечение: родители — лучшие 100 из 400 по Σ log P(истины) на общих эпизодах, по 4 потомка (турнир).
Правда (W) нужна отбору — это обратная связь среды; оценка — на отдельных тестовых эпизодах.
Теория: веса логистической регрессии максимального правдоподобия (ML) на 10⁶ эпизодах; наивная формула logit(r).

Запуск: python3 exp_trust_01.py [--pilot]. Результаты: results_trust_01.json. Предрегистрация: PREREG-TRUST-01.md.
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PI = 0.3
R_IND = np.array([0.55, 0.65, 0.75, 0.85, 0.92])
COPY_OF, COPY_P = 2, 0.8
NAMES = ['w0', 'r0.55', 'r0.65', 'r0.75', 'r0.85', 'r0.92', 'COPY(r0.75)']
N_POP, N_PAR, L_EP, G, SIG = 400, 100, 40, 1500, 0.04
SEEDS = list(range(300, 310))
PILOT_SEED = 998
SHIFT = 0.10                     # проверка вне диапазона: все надёжности на 0,1 ниже


def episodes(rng, n, shift=0.0):
    """Матрица признаков [1, x_1..x_6] (n × 7) и W (n)."""
    W = (rng.random(n) < PI).astype(int)
    s = 2 * W - 1
    r = R_IND - shift
    ok = rng.random((n, 5)) < r                    # источник прав?
    x = np.where(ok, 1, -1) * s[:, None]
    copy_ok = rng.random(n) < (R_IND[COPY_OF] - shift)
    indep = np.where(copy_ok, 1, -1) * s
    is_copy = rng.random(n) < COPY_P
    xc = np.where(is_copy, x[:, COPY_OF], indep)
    X = np.concatenate([np.ones((n, 1)), x, xc[:, None]], axis=1).astype(float)
    return X, W


def logistic_ml(X, W, iters=30):
    """Логистическая регрессия ML (Ньютон), без регуляризации."""
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(X @ w)))
        g = X.T @ (W - p)
        H = (X * (p * (1 - p))[:, None]).T @ X
        w += np.linalg.solve(H, g)
    return w


def metrics(w, X, W):
    z = X @ w
    p1 = 1 / (1 + np.exp(-z))
    pt = np.where(W == 1, p1, 1 - p1)
    acc = float(np.mean((z > 0) == (W == 1)))
    conf = float(np.mean(np.maximum(p1, 1 - p1)))
    ll = float(-np.mean(np.log(np.clip(pt, 1e-300, 1))))
    brier = float(np.mean((p1 - W) ** 2))
    pb = np.maximum(p1, 1 - p1); hit = ((z > 0) == (W == 1))
    bins = np.minimum((pb - 0.5) / 0.05, 9).astype(int)          # 10 корзин уверенности 0,5…1
    ece = float(sum(abs(pb[bins == b].mean() - hit[bins == b].mean()) * np.mean(bins == b)
                    for b in range(10) if np.any(bins == b)))
    return dict(acc=acc, conf=conf, self_dec=conf - acc, ignorance=1 - acc,
                deception=max(0.0, conf - acc), logloss=ll, brier=brier, ece=ece)


ARMS = ('KELLY', 'INDEP', 'ACC', 'CONTEST')


def log_true(Z, W):
    """log P(истины) для z (любой формы) и W той же формы или транслируемой."""
    return np.where(W == 1, -np.logaddexp(0, -Z), -np.logaddexp(0, Z))


def evolve(seed, arm, gens=G, track_every=10):
    rng = np.random.default_rng(seed * 10 + ARMS.index(arm))
    vrng = np.random.default_rng(seed + 50_000)
    Xv, Wv = episodes(vrng, 20_000)                                   # фиксированная проверка для траектории
    pop = rng.normal(0, 0.01, (N_POP, 7))
    traj = []
    for g in range(gens):
        if arm == 'INDEP':                                            # свои эпизоды у каждой особи
            X, W = episodes(rng, N_POP * L_EP)
            Z = np.einsum('nlk,nk->nl', X.reshape(N_POP, L_EP, 7), pop)
            logF = log_true(Z, W.reshape(N_POP, L_EP)).sum(1)
        else:
            X, W = episodes(rng, L_EP)
            Z = pop @ X.T                                             # N × L, эпизоды общие
            if arm == 'ACC':
                logF = ((Z > 0) == (W[None, :] == 1)).sum(1).astype(float)
            else:
                logF = log_true(Z, W[None, :]).sum(1)
        if arm == 'CONTEST':                                          # усечение: лучшие 100, по 4 потомка
            order = np.lexsort((rng.random(N_POP), -logF))
            parents = pop[order[:N_PAR]]
            pop = np.repeat(parents, N_POP // N_PAR, axis=0) + rng.normal(0, SIG, (N_POP, 7))
        else:                                                         # Райт–Фишер: потомки ∝ F = exp(logF)
            pr = np.exp(logF - logF.max()); pr /= pr.sum()
            idx = rng.choice(N_POP, size=N_POP, p=pr)
            pop = pop[idx] + rng.normal(0, SIG, (N_POP, 7))
        if g % track_every == 0 or g == gens - 1:
            wm = pop.mean(0)
            m = metrics(wm, Xv, Wv)
            traj.append(dict(g=g, w=wm.round(4).tolist(), scale=float(np.linalg.norm(wm[1:])),
                             spread=float(pop.std(0).mean()), acc=m['acc'], conf=m['conf'],
                             self_dec=m['self_dec'], logloss=m['logloss']))
    last = [t['w'] for t in traj if t['g'] >= gens - 300]
    w_final = np.mean(last, 0)
    trng = np.random.default_rng(seed + 90_000)
    Xt, Wt = episodes(trng, 200_000)
    Xs, Ws = episodes(trng, 200_000, shift=SHIFT)
    return dict(seed=seed, arm=arm, w_final=w_final.tolist(), test=metrics(w_final, Xt, Wt),
                shifted=metrics(w_final, Xs, Ws), traj=traj)


def theory(seed=12345):
    rng = np.random.default_rng(seed)
    X, W = episodes(rng, 1_000_000)
    w_ml = logistic_ml(X, W)
    lg = lambda p: np.log(p / (1 - p))
    w_naive = np.concatenate([[lg(PI)], lg(R_IND), [lg(R_IND[COPY_OF])]])
    trng = np.random.default_rng(seed + 1)
    Xt, Wt = episodes(trng, 200_000)
    Xs, Ws = episodes(trng, 200_000, shift=SHIFT)
    return dict(w_ml=w_ml.tolist(), w_naive=w_naive.tolist(), test_ml=metrics(w_ml, Xt, Wt),
                test_naive=metrics(w_naive, Xt, Wt), shifted_ml=metrics(w_ml, Xs, Ws))


def pilot():
    th = theory()
    print('ML   ', np.round(th['w_ml'], 3), {k: round(v, 4) for k, v in th['test_ml'].items()})
    print('наив.', np.round(th['w_naive'], 3), {k: round(v, 4) for k, v in th['test_naive'].items()})
    for arm in ARMS:
        t0 = time.time()
        r = evolve(PILOT_SEED, arm)
        print(f'\n{arm}: {time.time() - t0:.1f} с; w_final', np.round(r['w_final'], 3))
        print('  тест', {k: round(v, 4) for k, v in r['test'].items()})
        print('  сдвиг', {k: round(v, 4) for k, v in r['shifted'].items()})
        for t in r['traj'][::15] + [r['traj'][-1]]:
            print(f"   g={t['g']:4d} масштаб {t['scale']:.3f} разброс {t['spread']:.3f} точн. {t['acc']:.3f} "
                  f"уверен. {t['conf']:.3f} самообман {t['self_dec']:+.3f} logloss {t['logloss']:.4f}  w {np.round(t['w'], 2)}")


if __name__ == '__main__':
    if '--pilot' in sys.argv:
        pilot(); sys.exit(0)
    dry = '--dry' in sys.argv                     # сухой прогон цепочки: зёрна 990–991, вывод в dry/
    seeds = [990, 991] if dry else SEEDS
    outdir = os.path.join(HERE, 'dry') if dry else HERE
    os.makedirs(outdir, exist_ok=True)
    t0 = time.time()
    th = theory()
    runs = [evolve(s, arm) for s in seeds for arm in ARMS]
    json.dump(dict(names=NAMES, theory=th, runs=runs, params=dict(PI=PI, R_IND=R_IND.tolist(), COPY_OF=COPY_OF,
              COPY_P=COPY_P, N_POP=N_POP, N_PAR=N_PAR, L_EP=L_EP, G=G, SIG=SIG, SHIFT=SHIFT), seconds=time.time() - t0),
              open(os.path.join(outdir, 'results_trust_01.json'), 'w'))
    print(f'готово за {time.time() - t0:.0f} с; анализ — analyze_trust_01.py')
