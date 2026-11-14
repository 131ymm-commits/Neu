#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-02 «показатель»: задаёт ли время появления сходства представлений (t_align) только старшая мода λ_max
или ещё и число почти равных старших мод. Гипотеза — HYPOTHESIS.md (ворота 1).

Мир — SELF-01 (exp_self_01.simulate) плюс видимость действия b другого агента: столбцы b·m_b и m_b, маска m_b —
свой поток (зерно + 40 000), вложенная, как маска a. При q_b = 0 мир побитно совпадает с SELF-01 (тест).
Вход у всех условий — 64 после отбеливания: помехи N(0, 1) добирают размерность (первые k столбцов матрицы 54
помех с зерна + 20 000, чтобы помехи были общими у условий блока).
Сети, шаг, меры (CKA на половинах зонда A/B, поведение, R² объектов, mkNN, перестановочный нуль) — код
SPECTRUM-01 (train_group повторён с другим миром; тест сверяет кривые побитно при помехах SPECTRUM-01).
Режим — только богатый (lin2_small SELF-02: 300 шагов, шаг 0,1, инициализация 10⁻³).

  python3 spectrum02.py --pilot [--blocks K] [--jobs N]   блоки пилота (зёрна 159000+) → pilot/pilot.json (K = 2) или pilot/pilot_K.json
  python3 spectrum02.py --run [--jobs N]     блоки теста (151000+) → run/results.json
"""
import json
import os
import sys
import time

import numpy as np
from joblib import Parallel, delayed
from scipy.signal import lfilter
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '2026-11-13_SPECTRUM-01'))
sys.path.insert(0, os.path.join(HERE, '..', '2026-10-27_SELF-01'))
sys.path.insert(0, os.path.join(HERE, '..', '2026-10-28_SELF-02'))
import exp_self_01 as s1  # noqa: E402  мир SELF-01
import exp_self_02 as s2  # noqa: E402  r2_objects, ARMS
import spectrum01 as S1   # noqa: E402  меры и шаг обучения SPECTRUM-01

N_TR, N_TE = s1.N_TR, s1.N_TE
D_IN = 64                                  # вход после отбеливания у всех условий
N_NUIS_MAX = 54                            # помех не больше 54 (при q_a = q_b = 0 сигнал — 10 столбцов)
WIDTHS = S1.WIDTHS
HALF, K_NN, N_KNN, N_PERM = S1.HALF, S1.K_NN, S1.N_KNN, S1.N_PERM
RICH = S1.REGIMES['rich']                  # (model, steps, lr, init) = s2.ARMS['lin2_small']
TEST_BASE, PILOT_BASE, UNIT_BASE = 151000, 159000, 158000
N_BLOCKS = 10                              # число блоков теста — уточняется в PREREG по мощности
N_PILOT_MAX = 6                            # пилот не больше 6 блоков (зёрна 159000–159553)
B_MASK_OFF = 40_000
# условия: имя → (q_a, q_b)
CONDS = {'A0': (0.0, 0.0), 'A13': (1 / 3, 0.0), 'A23': (2 / 3, 0.0), 'A1': (1.0, 0.0),
         'AB13': (1 / 3, 1 / 3), 'AB23': (2 / 3, 2 / 3), 'AB1': (1.0, 1.0), 'B1': (0.0, 1.0)}


def simulate2(seed, qa, qb):
    """Ровно exp_self_01.simulate(seed, qa); при qb > 0 — ещё столбцы b·m_b, m_b и вклад b в P объектов 2 и 3."""
    rng = np.random.default_rng(seed)
    T, burn = N_TR + N_TE, 200
    n = T + burn + 1
    a = rng.standard_normal((n, 2))
    b = rng.standard_normal((n, 2))
    eta = rng.standard_normal((n, 5, 2))
    C = s1.COUPLE
    drive = np.zeros((n, 5, 2))
    drive[:, 0] = a
    drive[:, 1] = a
    drive[:, 2] = b
    drive[:, 3] = b
    inc = C[None, :, None] * drive + np.sqrt(1 - C ** 2)[None, :, None] * eta
    x = np.zeros((n, 5, 2))
    x[1:] = lfilter([1.0], [1.0, -s1.RHO], inc[:-1], axis=0)
    m = (np.random.default_rng(seed + 10_000).random(n) < qa).astype(float)
    x0, x1 = x[burn:burn + T], x[burn + 1:burn + T + 1]
    a0, m0 = a[burn:burn + T], m[burn:burn + T, None]
    cols = [x0.reshape(T, 10), a0 * m0, m0]
    P = s1.RHO * x0
    P[:, 0] += C[0] * a0 * m0
    P[:, 1] += C[1] * a0 * m0
    if qb > 0:
        mb = (np.random.default_rng(seed + B_MASK_OFF).random(n) < qb).astype(float)
        b0, mb0 = b[burn:burn + T], mb[burn:burn + T, None]
        cols += [b0 * mb0, mb0]
        P[:, 2] += C[2] * b0 * mb0
        P[:, 3] += C[3] * b0 * mb0
    return np.concatenate(cols, axis=1), x1.reshape(T, 10), P.reshape(T, 10)


def signal_dims(qa, qb):
    """Столбцов сигнала после отбеливания: постоянная маска (q = 1) и нулевые столбцы (q = 0) отбрасываются."""
    d = 10
    for q in (qa, qb):
        if q > 0:
            d += 2 + (1 if q < 1 else 0)
    return d


def nuis64(seed, n, k):
    """k помех: первые k столбцов матрицы (n, 54) с зерна seed + 20 000 — общие у всех условий блока."""
    assert 0 <= k <= N_NUIS_MAX
    return np.random.default_rng(seed + 20_000).standard_normal((n, N_NUIS_MAX))[:, :k]


def prep_scalers(seed, qa, qb):
    X, Y, P = simulate2(seed, qa, qb)
    sx, sy = StandardScaler().fit(X[:N_TR]), StandardScaler().fit(Y[:N_TR])
    Xs, Ys, Ps = sx.transform(X), sy.transform(Y), sy.transform(P)
    return (Xs[:N_TR], Xs[N_TR:], Ys[:N_TR], Ys[N_TR:], Ps[:N_TR], Ps[N_TR:]), sx, sy


def theory2(seed, qa, qb):
    """Сила мод по кластерам — как exp_self_02.theory, но в мире simulate2 (без помех, как в SELF-02)."""
    (Xtr, _, Ytr, _, _, _), _, _ = prep_scalers(seed, qa, qb)
    mu, Wh = S1.whitener(Xtr)
    Xw = (Xtr - mu) @ Wh
    W = Xw.T @ Ytr / len(Xw)
    F = Xw @ W
    lam = {}
    for name, objs in (('S', (0, 1)), ('O', (2, 3)), ('B', (4,))):
        vals = []
        for c in (0, 1):
            cols = [2 * i + c for i in objs]
            Cb = np.atleast_2d(np.cov(F[:, cols].T))
            vals.append(float(np.linalg.eigvalsh(Cb).max()))
        lam[name] = float(np.mean(vals))
    return lam


def run_data(seed, qa, qb, nuis_fn):
    (Xtr, Xte, Ytr, Yte, Ptr, Pte), sx, sy = prep_scalers(seed, qa, qb)
    k = D_IN - signal_dims(qa, qb)
    Nz = nuis_fn(seed, N_TR + N_TE, k)
    Xtr, Xte = np.hstack([Xtr, Nz[:N_TR]]), np.hstack([Xte, Nz[N_TR:]])
    mu, Wh = S1.whitener(Xtr)
    return dict(Xw=(Xtr - mu) @ Wh, Xtew=(Xte - mu) @ Wh, Y=Ytr, Ptr=Ptr, Pte=Pte, sx=sx, sy=sy, mu=mu, Wh=Wh, k=k)


def probe_raw(probe_seed, qa, qb, nuis_fn):
    X, _, P = simulate2(probe_seed, qa, qb)
    k = D_IN - signal_dims(qa, qb)
    return X[N_TR:], P[N_TR:], nuis_fn(probe_seed, N_TR + N_TE, k)[N_TR:]


def train_group(base, b, cond, nuis_fn=nuis64, self_curve=False):
    """Четыре сети блока b в условии cond одновременно — шаг и меры ровно как S1.train_group (богатый режим)."""
    qa, qb = CONDS[cond]
    model, steps, lr, init = RICH
    data, inits, pseed = S1.block_seeds(base, b)
    Xp_raw, Pp_raw, Np = probe_raw(pseed, qa, qb, nuis_fn)
    nets = []
    for r in range(4):
        dr = run_data(data[r], qa, qb, nuis_fn)
        n, d = dr['Xw'].shape
        h = WIDTHS[r]
        rng = np.random.default_rng(inits[r])
        sc1, sc2 = (init, init) if init > 0 else (1 / np.sqrt(d), 1 / np.sqrt(h))
        W1 = rng.standard_normal((d, h)) * sc1
        W2 = rng.standard_normal((h, 10)) * sc2
        M_ols = dr['Xw'].T @ dr['Y'] / n
        nets.append(dict(dr=dr, W1=W1, W2=W2, Xp=S1.to_run(dr, Xp_raw, Np), Pp=dr['sy'].transform(Pp_raw),
                         ref=s2.r2_objects(dr['Ptr'], dr['Xw'] @ M_ols), d=d, h=h, self_curve=[]))
    pairs = [(i, j) for i in range(4) for j in range(i + 1, 4)]
    cps = set(S1.checkpoints(steps))
    rec = dict(step=[], ckaA=[], ckaB=[], behav=[], r2=[])

    def snap(t):
        H = [nt['Xp'] @ nt['W1'] for nt in nets]
        Yh = [Hk @ nt['W2'] for Hk, nt in zip(H, nets)]
        Yraw = [nt['dr']['sy'].inverse_transform(Yk) for Yk, nt in zip(Yh, nets)]
        rec['step'].append(t)
        rec['ckaA'].append([S1.cka(H[i][:HALF], H[j][:HALF]) for i, j in pairs])
        rec['ckaB'].append([S1.cka(H[i][HALF:], H[j][HALF:]) for i, j in pairs])
        rec['behav'].append([S1.behav(Yraw[i][HALF:], Yraw[j][HALF:]) for i, j in pairs])
        rec['r2'].append([s2.r2_objects(nt['Pp'], Yk) for nt, Yk in zip(nets, Yh)])
        return H

    H0 = snap(0)
    mk0 = [S1.mknn(H0[i][:N_KNN], H0[j][:N_KNN]) for i, j in pairs]
    H = H0
    for t in range(1, steps + 1):
        for nt in nets:                                   # шаг ровно как S1.train_group / exp_self_02.train_curve ('lin2')
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
    mkT = [S1.mknn(H[i][:N_KNN], H[j][:N_KNN]) for i, j in pairs]
    g = np.random.default_rng([base + 100 * b + 99, list(CONDS).index(cond)])
    perm = []
    for i, j in pairs:                                    # перестановочный нуль на последнем шаге, половина B
        A, B = H[i][HALF:], H[j][HALF:]
        null = [S1.cka(A, B[g.permutation(len(B))]) for _ in range(N_PERM)]
        perm.append([float(np.mean(null)), float(np.std(null)), float(max(null))])
    out = dict(base=base, block=b, cond=cond, qa=qa, qb=qb, q=qa, regime='rich', d_nuis=nets[0]['dr']['k'], extra=0,
               data_seeds=data, init_seeds=inits, probe_seed=pseed, widths=WIDTHS, d_in=[nt['d'] for nt in nets],
               ref=[nt['ref'] for nt in nets], pairs=pairs, mknn0=mk0, mknnT=mkT, perm=perm,
               theory=[theory2(s, qa, qb) for s in data], **rec)
    if self_curve:
        out['self_curve'] = [np.array(nt['self_curve']).tolist() for nt in nets]
    return out


def jobs(base, n_blocks):
    return [(base, b, c) for b in range(n_blocks) for c in CONDS]


def summary_line(r):
    ck = np.array(r['ckaB']).mean(1)
    A = np.array(r['ckaA']).mean(1)
    st = r['step']
    thr = A[0] + 0.5 * (A[-1] - A[0])
    ta = next((st[k] for k, v in enumerate(ck) if v >= thr), None)
    lam = {k: round(float(np.mean([t[k] for t in r['theory']])), 3) for k in ('S', 'O', 'B')}
    return (f"b{r['block']} {r['cond']:5s} d_in={r['d_in'][0]} CKA {ck[0]:.3f}→{ck[-1]:.3f}  "
            f"mkNN {np.mean(r['mknn0']):.3f}→{np.mean(r['mknnT']):.3f}  t_align≈{ta}  λ {lam}")


def main():
    nj = int(sys.argv[sys.argv.index('--jobs') + 1]) if '--jobs' in sys.argv else 2
    if '--pilot' in sys.argv:                            # пилот: блоки 0–1, затем расширен до 6 для оценки разброса
        nb = int(sys.argv[sys.argv.index('--blocks') + 1]) if '--blocks' in sys.argv else 2
        base, out = PILOT_BASE, os.path.join(HERE, 'pilot', 'pilot.json' if nb == 2 else f'pilot_{nb}.json')
    elif '--run' in sys.argv:
        base, nb, out = TEST_BASE, N_BLOCKS, os.path.join(HERE, 'run', 'results.json')
    else:
        print(__doc__); sys.exit(2)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    t0 = time.time()
    R = Parallel(n_jobs=nj)(delayed(train_group)(*j) for j in jobs(base, nb))
    bad = [(r['block'], r['cond'], r['d_in']) for r in R if any(d != D_IN for d in r['d_in'])]
    if bad:
        sys.exit(f'вход после отбеливания не 64: {bad}')
    json.dump(dict(widths=WIDTHS, d_in=D_IN, regime=list(RICH), conds={k: list(v) for k, v in CONDS.items()},
                   half=HALF, k_nn=K_NN, n_knn=N_KNN, n_perm=N_PERM, groups=R, seconds=time.time() - t0),
              open(out, 'w'), ensure_ascii=False)
    for r in R:
        print(summary_line(r))
    print(f'готово за {time.time() - t0:.0f} с → {out}')


if __name__ == '__main__':
    main()
