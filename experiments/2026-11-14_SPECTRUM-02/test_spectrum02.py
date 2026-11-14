#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-02: тесты до пилота (сверка по коду, урок № 25).
1. simulate2(seed, q, 0) = exp_self_01.simulate(seed, q) побитно.
2. При q_b > 0: добавочные столбцы — ровно b·m_b и m_b; вклад b в P объектов 2 и 3; маски вложенные.
3. theory2(seed, q, 0) = exp_self_02.theory(seed, q).
4. Вход после отбеливания — 64 во всех условиях.
5. Обучение и меры: train_group с помехами SPECTRUM-01 = spectrum01.train_group побитно (A1 ↔ q = 1, помех 52;
   A0 ↔ q0_d64, помех 52 + 2). Тест: 30 блоков × 10 условий = 300 групп (совет 50, п. 5); мера фазы: 0 в начале, ≈ 1 в конце.
6. Потоки случайных чисел не пересекаются (тест, пилот, юнит-блок, SPECTRUM-01, SELF-01/02).
7. Симметрия: при B1 λ_O близка к λ_S при A1; λ_max(AB1) близка к λ_max(A1)."""
import sys

import numpy as np

import spectrum02 as S

FAIL = []


def check(c, msg):
    print(('  ✓ ' if c else '  ✗ ') + msg)
    if not c:
        FAIL.append(msg)


def t_world():
    for q in (0.0, 1 / 3, 1.0):
        a, b = S.s1.simulate(7, q), S.simulate2(7, q, 0.0)
        check(all(np.array_equal(u, v) for u, v in zip(a, b)), f'simulate2(q_a={q:.3f}, q_b=0) = SELF-01 побитно')
    X0, Y0, P0 = S.simulate2(7, 1.0, 0.0)
    X1, Y1, P1 = S.simulate2(7, 1.0, 2 / 3)
    rng = np.random.default_rng(7)
    T, burn = S.N_TR + S.N_TE, 200
    n = T + burn + 1
    rng.standard_normal((n, 2))
    b = rng.standard_normal((n, 2))
    mb = (np.random.default_rng(7 + S.B_MASK_OFF).random(n) < 2 / 3).astype(float)
    b0, mb0 = b[burn:burn + T], mb[burn:burn + T, None]
    check(np.array_equal(X1[:, :X0.shape[1]], X0) and np.array_equal(X1[:, X0.shape[1]:], np.hstack([b0 * mb0, mb0])),
          'q_b > 0: первые столбцы как без b, добавочные — b·m_b и m_b')
    dP = (P1 - P0).reshape(T, 5, 2)
    C = S.s1.COUPLE
    check(np.allclose(dP[:, 2], C[2] * b0 * mb0) and np.allclose(dP[:, 3], C[3] * b0 * mb0)
          and not dP[:, [0, 1, 4]].any() and np.array_equal(Y0, Y1), 'вклад b в P — только объекты 2 и 3; Y не меняется')
    m13 = np.random.default_rng(7 + S.B_MASK_OFF).random(n) < 1 / 3
    check(not (m13 & ~(mb > 0)).any(), 'маски b вложенные (⅓ ⊂ ⅔)')


def t_theory():
    for q in (0.0, 1.0):
        a, b = S.s2.theory(9, q), S.theory2(9, q, 0.0)
        check(all(abs(a[k] - b[k]) < 1e-10 for k in a), f'theory2(q={q}) = exp_self_02.theory ({a} / {b})')


def t_dims():
    for c, (qa, qb) in S.CONDS.items():
        dr = S.run_data(S.UNIT_BASE + 3, qa, qb, S.nuis64)
        check(dr['Xw'].shape[1] == S.D_IN, f'{c}: вход после отбеливания {dr["Xw"].shape[1]} (помех {dr["k"]})')


def t_train():
    """Сверка с SPECTRUM-01 при его помехах: A1 ↔ (q = 1, 52, 0), A0 ↔ (q = 0, 52, 2)."""
    s1_nuis = lambda seed, n, k: S.S1.nuis(seed, n, 52, k - 52)        # noqa: E731
    for cond, (q, nz, ex) in (('A1', (1.0, 52, 0)), ('A0', (0.0, 52, 2))):
        mine = S.train_group(S.UNIT_BASE, 0, cond, nuis_fn=s1_nuis)
        ref = S.S1.train_group(S.UNIT_BASE, 0, q, 'rich', nz, ex)
        same = all(np.array_equal(np.array(mine[k]), np.array(ref[k])) for k in ('step', 'ckaA', 'ckaB', 'behav', 'r2', 'mknn0', 'mknnT', 'ref', 'd_in'))
        th = all(abs(mine['theory'][i][k] - ref['theory'][i][k]) < 1e-10 for i in range(4) for k in ('S', 'O', 'B'))
        check(same and th, f'{cond}: кривые CKA, поведение, R², mkNN и λ совпали со spectrum01.train_group')


def t_streams():
    used = {}
    bases = [(S.TEST_BASE, 30, 'тест (с запасом до 30 блоков)'), (S.PILOT_BASE, S.N_PILOT_MAX, 'пилот'), (S.UNIT_BASE, 1, 'юнит'),
             (S.S1.TEST_BASE, S.S1.N_BLOCKS, 'S01 тест'), (S.S1.PILOT_BASE, 2, 'S01 пилот'), (S.S1.PILOT_BASE + 5000, 1, 'S01 юнит')]
    offs = (0, 10_000, 20_000, 30_000, S.B_MASK_OFF)
    for base, nb, tag in bases:
        for b in range(nb):
            data, inits, pseed = S.S1.block_seeds(base, b)
            for sd in data + [pseed]:
                for off in offs:
                    used.setdefault(sd + off, []).append((tag, off, sd))
            for si in inits:
                used.setdefault(si, []).append((tag, 777, si - 777))
    for sd in list(range(0, 10)) + list(range(100, 110)) + list(range(200, 210)) + [990, 991, 999]:   # SELF-01/02
        for off in (0, 777, 10_000):
            used.setdefault(sd + off, []).append(('SELF', off, sd))
    clash = {k: v for k, v in used.items() if len(v) > 1}
    check(not clash, f'потоки случайных чисел не пересекаются ({len(used)} потоков; пересечений {len(clash)})')


def t_jobs():
    J = S.jobs(S.TEST_BASE, S.N_BLOCKS)
    check(S.N_BLOCKS == 30 and len(J) == 300 and len(set(J)) == 300, f'тест: {S.N_BLOCKS} блоков × {len(S.CONDS)} условий = {len(J)} групп')


def t_phase():
    g = S.train_group(S.UNIT_BASE, 1, 'A1')
    lf = np.array(g['loss_frac']).mean(1)
    nS = np.array(g['norm_S']).mean(1)
    check(abs(lf[0]) < 1e-9 and lf[-1] > 0.95 and nS[0] < 0.01 and nS[-1] > 0.95,
          f'мера фазы: доля снятого лосса {lf[0]:.2e} → {lf[-1]:.3f}, норма S {nS[0]:.4f} → {nS[-1]:.3f}')


def t_symmetry():
    sd = S.UNIT_BASE + 2
    a1, b1, ab1 = S.theory2(sd, 1.0, 0.0), S.theory2(sd, 0.0, 1.0), S.theory2(sd, 1.0, 1.0)
    check(abs(b1['O'] / a1['S'] - 1) < 0.03, f'симметрия: λ_O(B1) = {b1["O"]:.3f} ≈ λ_S(A1) = {a1["S"]:.3f}')
    check(abs(max(ab1.values()) / max(a1.values()) - 1) < 0.03 and abs(ab1['O'] / ab1['S'] - 1) < 0.03,
          f'AB1: λ_S = {ab1["S"]:.3f}, λ_O = {ab1["O"]:.3f}; λ_max ≈ λ_max(A1) = {max(a1.values()):.3f}')


if __name__ == '__main__':
    t_world(); t_theory(); t_dims(); t_streams(); t_jobs(); t_symmetry(); t_phase(); t_train()
    print('ПРОВАЛОВ:', len(FAIL))
    sys.exit(1 if FAIL else 0)
