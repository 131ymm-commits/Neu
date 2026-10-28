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
  CONTEST — усечение: родители — лучшие 100 из 400 по Σ log P(истины) на общих эпизодах, по 4 потомка (турнир);
  KLUCK   — контроль к INDEP (предложил проверяющий по трём линзам): как KELLY, плюс «везение» — лог-счёт
            СРЕДНЕГО генотипа на собственных эпизодах особи; шум отбора как у INDEP, но от весов особи не зависит;
  KELLY6  — контроль к CONTEST: как KELLY, но отбор ∝ F⁶ (сила отбора близка к усечению 1 из 4).
Правда (W) нужна отбору — это обратная связь среды; оценка — точным перебором всех 128 состояний мира
(основная) и на 200 000 тестовых эпизодов (второй способ).
Теория: точные байесовские веса в закрытой форме (основная) и логистическая регрессия ML на 10⁶ эпизодах (второй способ).

Запуск: python3 exp_trust_01.py [--pilot | --dry]. Результаты: results_trust_01.json. Предрегистрация: PREREG-TRUST-01.md.
"""
import itertools
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
SHIFT = 0.10                     # проверка вне диапазона: все надёжности на 0,1 ниже (источник 0,55 становится 0,45 — сбивающим)
ARMS = ('KELLY', 'INDEP', 'ACC', 'CONTEST', 'KLUCK', 'KELLY6')
WINDOW = 300                     # итоговые веса — среднее снимков генотипа за последние 300 поколений (1200…1490 и 1499)


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


def log_true(Z, W):
    """log P(истины) для z (любой формы) и W той же формы или транслируемой; устойчиво при больших |z|."""
    return np.where(W == 1, -np.logaddexp(0, -Z), -np.logaddexp(0, Z))


def logistic_ml(X, W, iters=30):
    """Логистическая регрессия ML (Ньютон), без регуляризации."""
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(X @ w)))
        g = X.T @ (W - p)
        H = (X * (p * (1 - p))[:, None]).T @ X
        w += np.linalg.solve(H, g)
    return w


def _ece(conf, hit, mass):
    """ECE по 10 корзинам уверенности 0,5…1; conf, hit (доля верных в точке) и mass — по точкам."""
    bins = np.minimum((conf - 0.5) / 0.05, 9).astype(int)
    tot = 0.0
    for b in range(10):
        m = mass[bins == b].sum()
        if m > 0:
            tot += abs((conf[bins == b] * mass[bins == b]).sum() / m - (hit[bins == b] * mass[bins == b]).sum() / m) * m
    return float(tot)


def metrics(w, X, W):
    """Метрики на выборке эпизодов (второй способ)."""
    z = X @ w
    p1 = 1 / (1 + np.exp(-z))
    acc = float(np.mean((z > 0) == (W == 1)))
    conf = float(np.mean(np.maximum(p1, 1 - p1)))
    ll = float(-np.mean(log_true(z, W)))
    brier = float(np.mean((p1 - W) ** 2))
    pb = np.maximum(p1, 1 - p1); hit = ((z > 0) == (W == 1)).astype(float)
    ece = _ece(pb, hit, np.ones_like(pb) / len(pb))
    return dict(acc=acc, conf=conf, self_dec=conf - acc, ignorance=1 - acc,
                deception=max(0.0, conf - acc), logloss=ll, brier=brier, ece=ece)


PATTERNS = np.array(list(itertools.product([-1, 1], repeat=6)))     # x1..x5 и пересказ x6: 64 узора


def world_probs(shift=0.0):
    """P(W, узор) для всех 2 × 64 состояний мира."""
    r = R_IND - shift; rc = R_IND[COPY_OF] - shift
    out = []
    for Wv in (0, 1):
        s = 2 * Wv - 1
        pW = PI if Wv == 1 else 1 - PI
        px = np.where(PATTERNS[:, :5] == s, r, 1 - r).prod(1)
        x3, x6 = PATTERNS[:, COPY_OF], PATTERNS[:, 5]
        pc = COPY_P * (x6 == x3) + (1 - COPY_P) * np.where(x6 == s, rc, 1 - rc)
        out.append(pW * px * pc)
    P0, P1 = out
    assert abs(P0.sum() + P1.sum() - 1) < 1e-12
    return P0, P1


def exact_metrics(w, shift=0.0):
    """Метрики точным перебором всех состояний мира (основной способ)."""
    P0, P1 = world_probs(shift)
    X = np.concatenate([np.ones((64, 1)), PATTERNS], axis=1).astype(float)
    z = X @ np.asarray(w, float)
    p1 = 1 / (1 + np.exp(-z)); conf_pat = np.maximum(p1, 1 - p1); dec1 = z > 0
    mass = P0 + P1
    acc = float((P1 * dec1).sum() + (P0 * ~dec1).sum())
    conf = float((mass * conf_pat).sum())
    ll = float(-(P1 * log_true(z, 1) + P0 * log_true(z, 0)).sum())
    brier = float((P1 * (1 - p1) ** 2 + P0 * p1 ** 2).sum())
    hit = np.where(dec1, P1, P0) / mass
    return dict(acc=acc, conf=conf, self_dec=conf - acc, ignorance=1 - acc, deception=max(0.0, conf - acc),
                logloss=ll, brier=brier, ece=_ece(conf_pat, hit, mass))


def exact_weights():
    """Точные байесовские веса: апостериорные лог-шансы линейны по сигналам; у пары веса равны L/2, где
    L = log[r(c + (1 − c)r) / ((1 − r)(c + (1 − c)(1 − r)))] — согласие пары; при несогласии вклад 0."""
    lg = lambda p: np.log(p / (1 - p))
    r, c = R_IND[COPY_OF], COPY_P
    L = np.log(r * (c + (1 - c) * r) / ((1 - r) * (c + (1 - c) * (1 - r))))
    w = np.array([lg(PI), lg(R_IND[0]), lg(R_IND[1]), L / 2, lg(R_IND[3]), lg(R_IND[4]), L / 2])
    P0, P1 = world_probs()
    X = np.concatenate([np.ones((64, 1)), PATTERNS], axis=1).astype(float)
    post = np.log(P1 / P0)                                            # проверка: точная апостериорная лог-шансы
    assert np.allclose(X @ w, post, atol=1e-12)
    return w


def evolve(seed, arm, gens=G, track_every=10):
    rng = np.random.default_rng(seed * 10 + ARMS.index(arm))
    vrng = np.random.default_rng(seed + 50_000)
    Xv, Wv = episodes(vrng, 20_000)                                   # фиксированная проверка для траектории
    pop = rng.normal(0, 0.01, (N_POP, 7))
    traj, neff, sdF = [], [], []
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
            if arm == 'KLUCK':                                        # везение: средний генотип на своих эпизодах особи
                Xi, Wi = episodes(rng, N_POP * L_EP)
                zi = (Xi @ pop.mean(0)).reshape(N_POP, L_EP)
                logF = logF + log_true(zi, Wi.reshape(N_POP, L_EP)).sum(1)
            if arm == 'KELLY6':
                logF = 6.0 * logF
        sdF.append(float(logF.std()))
        if arm == 'CONTEST':                                          # усечение: лучшие 100, по 4 потомка
            order = np.lexsort((rng.random(N_POP), -logF))
            parents = pop[order[:N_PAR]]
            pop = np.repeat(parents, N_POP // N_PAR, axis=0) + rng.normal(0, SIG, (N_POP, 7))
            neff.append(float(N_PAR))
        else:                                                         # Райт–Фишер: потомки ∝ F = exp(logF)
            pr = np.exp(logF - logF.max()); pr /= pr.sum()
            neff.append(float(1 / (pr ** 2).sum()))
            idx = rng.choice(N_POP, size=N_POP, p=pr)
            pop = pop[idx] + rng.normal(0, SIG, (N_POP, 7))
        if g % track_every == 0 or g == gens - 1:
            wm = pop.mean(0)
            m = metrics(wm, Xv, Wv)
            traj.append(dict(g=g, w=wm.round(4).tolist(), spread=float(pop.std(0).mean()), acc=m['acc'],
                             conf=m['conf'], self_dec=m['self_dec'], logloss=m['logloss']))
    last = [t['w'] for t in traj if t['g'] >= gens - WINDOW]
    w_final = np.mean(last, 0)
    trng = np.random.default_rng(seed + 90_000)
    Xt, Wt = episodes(trng, 200_000)
    Xs, Ws = episodes(trng, 200_000, shift=SHIFT)
    late = slice(gens - WINDOW, gens)
    return dict(seed=seed, arm=arm, w_final=w_final.tolist(), n_snap=len(last),
                exact=exact_metrics(w_final), exact_shifted=exact_metrics(w_final, SHIFT),
                test=metrics(w_final, Xt, Wt), shifted=metrics(w_final, Xs, Ws),
                neff_late=float(np.median(neff[late])), sdF_late=float(np.median(sdF[late])), traj=traj)


def theory(seed=12345):
    rng = np.random.default_rng(seed)
    X, W = episodes(rng, 1_000_000)
    w_ml = logistic_ml(X, W)
    w_ex = exact_weights()
    lg = lambda p: np.log(p / (1 - p))
    w_naive = np.concatenate([[lg(PI)], lg(R_IND), [lg(R_IND[COPY_OF])]])
    trng = np.random.default_rng(seed + 1)
    Xt, Wt = episodes(trng, 200_000)
    return dict(w_exact=w_ex.tolist(), w_ml=w_ml.tolist(), w_naive=w_naive.tolist(),
                max_abs_ml_minus_exact=float(np.abs(w_ml - w_ex).max()),
                exact_exact=exact_metrics(w_ex), exact_shifted_exact=exact_metrics(w_ex, SHIFT),
                exact_ml=exact_metrics(w_ml), exact_naive=exact_metrics(w_naive),
                test_ml=metrics(w_ml, Xt, Wt))


def pilot():
    th = theory()
    print('точные', np.round(th['w_exact'], 4), {k: round(v, 4) for k, v in th['exact_exact'].items()})
    print('ML    ', np.round(th['w_ml'], 4), 'max|ML − точн.|', round(th['max_abs_ml_minus_exact'], 4))
    print('наив. ', np.round(th['w_naive'], 4), {k: round(v, 4) for k, v in th['exact_naive'].items()})
    print('точные после сдвига', {k: round(v, 4) for k, v in th['exact_shifted_exact'].items()})
    for arm in ARMS:
        t0 = time.time()
        r = evolve(PILOT_SEED, arm)
        print(f'\n{arm}: {time.time() - t0:.1f} с; N_eff (поздн. медиана) {r["neff_late"]:.1f}; SD(logF) {r["sdF_late"]:.2f}; '
              f'w_final', np.round(r['w_final'], 3))
        print('  точно ', {k: round(v, 4) for k, v in r['exact'].items()})
        print('  выборка', {k: round(v, 4) for k, v in r['test'].items()})
        print('  сдвиг (точно)', {k: round(v, 4) for k, v in r['exact_shifted'].items()})
        for t in r['traj'][::15] + [r['traj'][-1]]:
            print(f"   g={t['g']:4d} разброс {t['spread']:.3f} точн. {t['acc']:.3f} уверен. {t['conf']:.3f} "
                  f"самообман {t['self_dec']:+.3f}  w {np.round(t['w'], 2)}")


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
              COPY_P=COPY_P, N_POP=N_POP, N_PAR=N_PAR, L_EP=L_EP, G=G, SIG=SIG, SHIFT=SHIFT, WINDOW=WINDOW,
              ARMS=list(ARMS)), seconds=time.time() - t0),
              open(os.path.join(outdir, 'results_trust_01.json'), 'w'))
    print(f'готово за {time.time() - t0:.0f} с; анализ — analyze_trust_01.py')
