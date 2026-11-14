#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-01: тесты до пилота.
1. prep_scalers = s1.prep побитно (мир SELF-01 без изменений).
2. Без помех, ширина 64, init_seed = seed + 777: кривая R² на своём тесте = exp_self_02.train_curve (оба режима).
3. CKA: CKA(H, H) = 1; инвариантна к повороту и масштабу; для двух случайных проекций изотропных данных
   d → h ≈ h/(h + d) (теория для больших n).
4. mkNN: одинаковые представления → 1; независимые случайные → около k/n.
5. Зёрна теста и пилота не пересекаются между собой и с SELF-01/02."""
import sys
import numpy as np
import spectrum01 as S

FAIL = []


def check(c, msg):
    print(('  ✓ ' if c else '  ✗ ') + msg)
    if not c:
        FAIL.append(msg)


def t_world():
    for q in (0.0, 1.0):
        a = S.s1.prep(7, q)
        b, _, _ = S.prep_scalers(7, q)
        check(all(np.array_equal(u, v) for u, v in zip(a, b)), f'prep_scalers = s1.prep (q={q})')


def t_self02():
    """Сверка обучения с SELF-02: один блок без помех; сеть r = 2 имеет ширину 64."""
    for regime in ('rich', 'lazy'):
        out = S.train_group(S.PILOT_BASE + 5000, 0, 1.0, regime, 0, self_curve=True)
        r = 2
        seed = out['data_seeds'][r]
        model, steps, lr, init = S.s2.ARMS['lin2_small' if regime == 'rich' else 'lin2_lazy']   # шаги SELF-02
        ref_curve = S.s2.train_curve(seed, 1.0, model, steps, lr, init, h=64)[0]
        mine = np.array(out['self_curve'][r])[:steps]      # ленивый режим здесь длиннее: сверяются первые шаги SELF-02
        check(out['widths'][r] == 64 and out['init_seeds'][r] == seed + 777, f'{regime}: сеть 2 — ширина 64, init = seed + 777')
        check(mine.shape == ref_curve.shape and np.allclose(mine, ref_curve, atol=1e-10, rtol=0),
              f'{regime}: кривая R² совпала с exp_self_02.train_curve (макс. расхождение {np.abs(mine - ref_curve).max():.2e})')


def t_cka():
    g = np.random.default_rng(0)
    n, d = 4000, 64
    X = g.standard_normal((n, d))
    H = X @ g.standard_normal((d, 32))
    Q, _ = np.linalg.qr(g.standard_normal((32, 32)))
    check(abs(S.cka(H, H) - 1) < 1e-12, 'CKA(H, H) = 1')
    check(abs(S.cka(H, 3.7 * H @ Q) - 1) < 1e-10, 'CKA инвариантна к повороту и масштабу')
    for h in (32, 64, 96):
        vals = [S.cka(X @ g.standard_normal((d, h)), X @ g.standard_normal((d, h))) for _ in range(5)]
        th = h / (h + d)
        check(abs(np.mean(vals) - th) < 0.06, f'случайные проекции d={d} → h={h}: CKA {np.mean(vals):.3f} ≈ теория {th:.3f}')


def t_mknn():
    g = np.random.default_rng(1)
    A = g.standard_normal((1000, 16))
    check(abs(S.mknn(A, A) - 1) < 1e-12, 'mkNN(A, A) = 1')
    v = S.mknn(A, g.standard_normal((1000, 16)))
    check(v < 0.05, f'mkNN независимых ≈ k/n ({v:.3f}; k/n = {S.K_NN / 1000:.3f})')


def t_streams():
    """Совет 48, п. «в»: потоки случайных чисел не пересекаются. Для зерна выборки s: s (мир), s + 10000 (маска q),
    s + 20000 (помехи), s + 30000 (добавочные помехи q0_d64), s + 777 (инициализация); для зерна зонда — первые четыре."""
    used = {}
    bases = [(S.TEST_BASE, S.N_BLOCKS), (S.PILOT_BASE, 2), (S.PILOT_BASE + 5000, 1)]
    for base, nb in bases:
        for b in range(nb):
            data, inits, pseed = S.block_seeds(base, b)
            for sd in data + [pseed]:
                for off, tag in ((0, 'мир'), (10_000, 'маска'), (20_000, 'помехи'), (30_000, 'доб. помехи')):
                    used.setdefault(sd + off, []).append((tag, sd))
            for si in inits:
                used.setdefault(si, []).append(('инициализация', si - 777))
    clash = {k: v for k, v in used.items() if len(v) > 1}
    check(not clash, f'потоки случайных чисел не пересекаются ({len(used)} потоков; пересечений {len(clash)})')


def t_seeds():
    test = {s for b in range(S.N_BLOCKS) for s in S.block_seeds(S.TEST_BASE, b)[0] + [S.block_seeds(S.TEST_BASE, b)[2]]}
    pil = {s for b in range(2) for s in S.block_seeds(S.PILOT_BASE, b)[0] + [S.block_seeds(S.PILOT_BASE, b)[2]]}
    tst = {s for s in S.block_seeds(S.PILOT_BASE + 5000, 0)[0]}
    old = set(range(0, 10)) | set(range(100, 110)) | set(range(200, 210)) | {999, 990, 991}
    check(not (test & pil) and not (test & tst) and not (test & old) and not (pil & old), 'зёрна теста, пилота, тестов и SELF-01/02 не пересекаются')


if __name__ == '__main__':
    t_world(); t_cka(); t_mknn(); t_seeds(); t_streams(); t_self02()
    print('ПРОВАЛОВ:', len(FAIL))
    sys.exit(1 if FAIL else 0)
