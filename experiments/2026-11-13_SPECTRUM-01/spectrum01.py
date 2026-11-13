#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-01 «Я-СПЕКТР»: сходятся ли скрытые представления независимо обученных сетей в мире SELF
и появляется ли сходство вместе с самой сильной модой.

Мир — exp_self_01.simulate (SELF-01) плюс D_NUIS помех на входе (независимый N(0,1); без них геометрия
входа даёт сходство даром). Режимы и шаги — ARMS из exp_self_02 (SELF-02): богатый = lin2_small, ленивый =
lin2_lazy. Обучение — полный градиентный спуск на ½·MSE, как в exp_self_02.train_curve.

Блок = 4 сети с разными выборками мира (data_seed), инициализацией (init_seed = data_seed + 777, как в
SELF-02) и шириной (WIDTHS), обученные одновременно; общий зонд — отдельная выборка мира (probe_seed).
Меры на зонде: линейная CKA скрытых представлений между парами (6 пар), начальная линия — CKA на шаге 0;
перестановочный нуль на последнем шаге; взаимные k ближайших соседей (mkNN) на шаге 0 и в конце; сходство
поведения — выходы сетей в исходных единицах; R² объектов (как SELF-02).
Половины зонда: A (первые 2000) и B (вторые 2000) — порог времени по A, пересечение по B (урок EVO-06).

  python3 spectrum01.py --pilot          блоки пилота (зёрна 59000+), печать динамики → pilot/pilot.json
  python3 spectrum01.py --run            блоки теста (51000+) и контроль без помех → run/results.json
"""
import json
import os
import sys
import time

import numpy as np
from joblib import Parallel, delayed
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '2026-10-27_SELF-01'))
sys.path.insert(0, os.path.join(HERE, '..', '2026-10-28_SELF-02'))
import exp_self_01 as s1  # noqa: E402  мир SELF-01
import exp_self_02 as s2  # noqa: E402  режимы, r2_objects, theory — код SELF-02

N_TR, N_TE = s1.N_TR, s1.N_TE
D_NUIS = 52                          # помехи: d_вход = 12 + 52 = 64 при q = 1 (10 + 52 = 62 при q = 0)
WIDTHS = [32, 48, 64, 96]            # ширины четырёх сетей блока
QS = [0.0, 1.0]
LAZY_STEPS = 3000                    # после пилота: с помехами (d_вход 64) ленивая сеть учится в ~h/d раз медленнее,
                                     # за 600 шагов SELF-02 не доходит до потолка; шаг и инициализация — как в SELF-02
REGIMES = {'rich': s2.ARMS['lin2_small'],                                   # (model, steps, lr, init) — SELF-02
           'lazy': (s2.ARMS['lin2_lazy'][0], LAZY_STEPS) + tuple(s2.ARMS['lin2_lazy'][2:])}
HALF = N_TE // 2                     # половины зонда A и B
K_NN = 10
N_KNN = 2000                         # mkNN — на половине A
N_PERM = 100
TEST_BASE, PILOT_BASE = 51000, 59000
N_BLOCKS = 10


def block_seeds(base, b):
    data = [base + 100 * b + r for r in range(4)]
    return data, [s + 777 for s in data], base + 100 * b + 50


def prep_scalers(seed, q):
    """Ровно s1.prep, но со шкалами (нужны, чтобы перевести зонд и выходы)."""
    X, Y, P = s1.simulate(seed, q)
    sx, sy = StandardScaler().fit(X[:N_TR]), StandardScaler().fit(Y[:N_TR])
    Xs, Ys, Ps = sx.transform(X), sy.transform(Y), sy.transform(P)
    return (Xs[:N_TR], Xs[N_TR:], Ys[:N_TR], Ys[N_TR:], Ps[:N_TR], Ps[N_TR:]), sx, sy


def nuis(seed, n, d):
    return np.random.default_rng(seed + 20_000).standard_normal((n, d)) if d else np.zeros((n, 0))


def whitener(Xtr):
    """Как exp_self_02.whiten_data: PCA-отбеливание по обучающей части, отбрасывая собственные числа ≤ 1e-8·max."""
    C = np.cov(Xtr.T, bias=True)
    ev, V = np.linalg.eigh(C)
    keep = ev > 1e-8 * ev.max()
    return Xtr.mean(0), V[:, keep] / np.sqrt(ev[keep])


def run_data(seed, q, d_nuis):
    (Xtr, Xte, Ytr, Yte, Ptr, Pte), sx, sy = prep_scalers(seed, q)
    Nz = nuis(seed, N_TR + N_TE, d_nuis)
    Xtr, Xte = np.hstack([Xtr, Nz[:N_TR]]), np.hstack([Xte, Nz[N_TR:]])
    mu, Wh = whitener(Xtr)
    return dict(Xw=(Xtr - mu) @ Wh, Xtew=(Xte - mu) @ Wh, Y=Ytr, Ptr=Ptr, Pte=Pte, sx=sx, sy=sy, mu=mu, Wh=Wh)


def probe_raw(probe_seed, q, d_nuis):
    X, _, P = s1.simulate(probe_seed, q)
    return X[N_TR:], P[N_TR:], nuis(probe_seed, N_TR + N_TE, d_nuis)[N_TR:]


def to_run(dr, Xp_raw, Np):
    """Зонд в координатах сети: её шкала, помехи как есть, её отбеливание."""
    return (np.hstack([dr['sx'].transform(Xp_raw), Np]) - dr['mu']) @ dr['Wh']


def cka(A, B):
    A = A - A.mean(0)
    B = B - B.mean(0)
    den = np.linalg.norm(A.T @ A) * np.linalg.norm(B.T @ B)
    return float(np.linalg.norm(A.T @ B) ** 2 / den) if den > 0 else 0.0


def mknn(A, B, k=K_NN):
    """Взаимные k ближайших соседей (евклидово расстояние): средняя доля общих соседей."""
    def nn(Z):
        G = Z @ Z.T
        sq = np.diag(G)
        D = sq[:, None] + sq[None, :] - 2 * G
        np.fill_diagonal(D, np.inf)
        return np.argpartition(D, k, axis=1)[:, :k]
    na, nb = nn(A), nn(B)
    return float(np.mean([len(set(na[i]) & set(nb[i])) for i in range(len(A))]) / k)


def behav(Ya, Yb):
    """Сходство поведения: 1 − Σ(Ya − Yb)² / среднее Σ(Y − Ȳ)²; выходы в исходных единицах."""
    va, vb = ((Ya - Ya.mean(0)) ** 2).sum(), ((Yb - Yb.mean(0)) ** 2).sum()
    return float(1 - ((Ya - Yb) ** 2).sum() / (0.5 * (va + vb)))


def checkpoints(steps):
    return sorted(set(range(0, min(150, steps) + 1)) | set(range(150, min(600, steps) + 1, 5))
                  | set(range(600, steps + 1, 25)) | {steps})


def train_group(base, b, q, regime, d_nuis, self_curve=False):
    """Четыре сети блока b одновременно. self_curve — кривая R² на своём тесте (для сверки с SELF-02)."""
    model, steps, lr, init = REGIMES[regime]
    data, inits, pseed = block_seeds(base, b)
    Xp_raw, Pp_raw, Np = probe_raw(pseed, q, d_nuis)
    nets = []
    for r in range(4):
        dr = run_data(data[r], q, d_nuis)
        n, d = dr['Xw'].shape
        h = WIDTHS[r]
        rng = np.random.default_rng(inits[r])
        sc1, sc2 = (init, init) if init > 0 else (1 / np.sqrt(d), 1 / np.sqrt(h))
        W1 = rng.standard_normal((d, h)) * sc1
        W2 = rng.standard_normal((h, 10)) * sc2
        M_ols = dr['Xw'].T @ dr['Y'] / n
        nets.append(dict(dr=dr, W1=W1, W2=W2, Xp=to_run(dr, Xp_raw, Np), Pp=dr['sy'].transform(Pp_raw),
                         ref=s2.r2_objects(dr['Ptr'], dr['Xw'] @ M_ols), d=d, h=h, self_curve=[]))
    pairs = [(i, j) for i in range(4) for j in range(i + 1, 4)]
    cps = set(checkpoints(steps))
    rec = dict(step=[], ckaA=[], ckaB=[], behav=[], r2=[])

    def snap(t):
        H = [nt['Xp'] @ nt['W1'] for nt in nets]
        Yh = [Hk @ nt['W2'] for Hk, nt in zip(H, nets)]
        Yraw = [nt['dr']['sy'].inverse_transform(Yk) for Yk, nt in zip(Yh, nets)]
        rec['step'].append(t)
        rec['ckaA'].append([cka(H[i][:HALF], H[j][:HALF]) for i, j in pairs])
        rec['ckaB'].append([cka(H[i][HALF:], H[j][HALF:]) for i, j in pairs])
        rec['behav'].append([behav(Yraw[i][HALF:], Yraw[j][HALF:]) for i, j in pairs])
        rec['r2'].append([s2.r2_objects(nt['Pp'], Yk) for nt, Yk in zip(nets, Yh)])
        return H

    H0 = snap(0)
    mk0 = [mknn(H0[i][:N_KNN], H0[j][:N_KNN]) for i, j in pairs]
    for t in range(1, steps + 1):
        for nt in nets:                                   # шаг ровно как exp_self_02.train_curve ('lin2')
            Z = nt['dr']['Xw'] @ nt['W1']
            E = Z @ nt['W2'] - nt['dr']['Y']
            gW2 = Z.T @ E / len(Z)
            gW1 = nt['dr']['Xw'].T @ (E @ nt['W2'].T) / len(Z)
            nt['W1'] -= lr * gW1
            nt['W2'] -= lr * gW2
            if self_curve:
                nt['self_curve'].append(s2.r2_objects(nt['dr']['Pte'], nt['dr']['Xtew'] @ nt['W1'] @ nt['W2']))
        if t in cps:
            H = snap(t)
    mkT = [mknn(H[i][:N_KNN], H[j][:N_KNN]) for i, j in pairs]
    g = np.random.default_rng(base + 100 * b + 99 + int(q * 10) + (0 if regime == 'rich' else 5))
    perm = []
    for i, j in pairs:                                    # перестановочный нуль на последнем шаге, половина B
        A, B = H[i][HALF:], H[j][HALF:]
        null = [cka(A, B[g.permutation(len(B))]) for _ in range(N_PERM)]
        perm.append([float(np.mean(null)), float(np.std(null)), float(max(null))])
    out = dict(base=base, block=b, q=q, regime=regime, d_nuis=d_nuis, data_seeds=data, init_seeds=inits, probe_seed=pseed,
               widths=WIDTHS, d_in=[nt['d'] for nt in nets], ref=[nt['ref'] for nt in nets], pairs=pairs,
               mknn0=mk0, mknnT=mkT, perm=perm,
               theory=[s2.theory(s, q) for s in data], **rec)
    if self_curve:
        out['self_curve'] = [np.array(nt['self_curve']).tolist() for nt in nets]
    return out


def jobs(base, n_blocks, with_control):
    J = [(base, b, q, rg, D_NUIS) for b in range(n_blocks) for q in QS for rg in REGIMES]
    if with_control:                                     # контроль метода: без помех, q = 1
        J += [(base, b, 1.0, rg, 0) for b in range(n_blocks) for rg in REGIMES]
    return J


def summary_line(r):
    ck = np.array(r['ckaB']).mean(1)
    bh = np.array(r['behav']).mean(1)
    st = r['step']
    i50 = next((k for k, v in enumerate(ck) if v >= ck[0] + 0.5 * (ck[-1] - ck[0])), None)
    return (f"b{r['block']} q={r['q']} {r['regime']:4s} nuis={r['d_nuis']:2d}  CKA {ck[0]:.3f}→{ck[-1]:.3f}  "
            f"mkNN {np.mean(r['mknn0']):.3f}→{np.mean(r['mknnT']):.3f}  поведение {bh[-1]:.3f}  "
            f"t½(CKA) {st[i50] if i50 is not None else '—'}  нуль {np.mean([p[0] for p in r['perm']]):.4f}")


def main():
    if '--pilot' in sys.argv:
        base, nb, ctrl, out = PILOT_BASE, 2, True, os.path.join(HERE, 'pilot', 'pilot.json')
    elif '--run' in sys.argv:
        base, nb, ctrl, out = TEST_BASE, N_BLOCKS, True, os.path.join(HERE, 'run', 'results.json')
    else:
        print(__doc__); sys.exit(2)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    t0 = time.time()
    R = Parallel(n_jobs=2)(delayed(train_group)(*j) for j in jobs(base, nb, ctrl))
    json.dump(dict(widths=WIDTHS, d_nuis=D_NUIS, regimes={k: list(v) for k, v in REGIMES.items()}, half=HALF,
                   k_nn=K_NN, n_knn=N_KNN, n_perm=N_PERM, groups=R, seconds=time.time() - t0),
              open(out, 'w'), ensure_ascii=False)
    for r in R:
        print(summary_line(r))
    print(f'готово за {time.time() - t0:.0f} с → {out}')


if __name__ == '__main__':
    main()
