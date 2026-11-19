#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04 «ПРОЧИЕ» (HYPOTHESIS.md, 11ae9f8c): программа-М — та же формула потери переноса и та же доля ε «прочих», что программа
DISTILL-02, но «прочие» ответы — смесь операторов f(a, b) с весами головы вместо таблицы частот смещений.
  Q_М(y | a, b) = [Σ_k π_k · 1[y ∈ C'_k] / |C'_k| + π_U / |V|] / Z,   C'_k = C_k(a, b) без опоры переноса S, Z = Σ_{k: C'_k ≠ ∅} π_k + π_U.
  Веса π — максимум правдоподобия на «прочих» ответах головы на построении (softmax, L-BFGS, точная нормировка Z).
  Нуль-Т (совет 77) — таблица частот с тем же числом свободных параметров: K самых частых «прочих» смещений и остаток на |V|
    (K = число операторов каталога). Программа DISTILL-02 — таблица из 30 (описательно); М+Т — операторы и таблица из 30 − K (описательно).
  Каталог — правило записки разведки (NOTE-explore.md §5): оператор входит, если хоть у одной головы хоть одного семейства он объясняет
  не меньше CATALOG_MIN «прочих» ответов на построении. Считается по построению, тест не читается.
Ответы голов — только числа; ничего из них не исполняется."""
import json
import math
import os
import sys
import time

import numpy as np

X_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X_DIR))
sys.path.insert(0, os.path.join(ROOT, 'experiments', '2026-11-18_DISTILL-02'))
sys.path.insert(0, X_DIR)
import distill02 as D2  # noqa: E402
import explore_d4 as XE  # noqa: E402

NC = D2.NC
CANDIDATE_OPS = XE.OPS + ('clamp9',)        # clamp9 — «зажим» у перехода через сотню a (NOTE-explore.md §3, найден по примерам)
CATALOG_MIN = 0.01                          # правило каталога (NOTE-explore.md §5)
TABLE_FULL = D2.TOP_OFFSETS                 # 30 — таблица программы DISTILL-02


def candidates(a, b):
    """Операторы разведки и clamp9: y = 100·⌊a/100⌋ + 90 + (s mod 10), если s перешла через сотню a."""
    c = XE.candidates(a, b)
    s, base = a + b, 100 * (a // 100)
    c['clamp9'] = {base + 90 + s % 10} - {s} if s >= base + 100 else set()
    return c


def support(prog, it):
    """Опора части переноса: верный ответ и ответы с потерей переносов (как ключи distill02.program_dist)."""
    return set(D2.program_dist(prog, it, True))


def other_rows(items, offs, prog, ops):
    """«Прочие» ответы головы: для каждого — a_ik = 1[y ∈ C'_k]/|C'_k|, z_ik = 1[C'_k ≠ ∅], u_i = 1/|V|."""
    A, Zm, U = [], [], []
    for it, d in zip(items, offs):
        if d >= NC or d == 0:
            continue
        S = support(prog, it)
        y = it['sum'] + int(d)
        if y in S:
            continue
        cand = candidates(it['a'], it['b'])
        row_a, row_z = [], []
        for op in ops:
            ck = cand[op] - S
            row_z.append(1.0 if ck else 0.0)
            row_a.append(1.0 / len(ck) if y in ck else 0.0)
        A.append(row_a)
        Zm.append(row_z)
        U.append(1.0 / D2.ref_size(it['sum']))
    k = len(ops)
    return np.array(A, float).reshape(-1, k), np.array(Zm, float).reshape(-1, k), np.array(U, float)


def fit_weights(A, Zm, U, iters=500):
    """π (K операторов и остаток) — максимум Σ log(A·π + u π_U) − log(Z·π + π_U) при π = softmax(θ); L-BFGS с точным градиентом
    ∂ℓ/∂θ_m = π_m Σ_i [Ã_im/(Ã_i·π) − Z̃_im/(Z̃_i·π)]. Без «прочих» — все веса на остатке."""
    from scipy.optimize import minimize
    k = A.shape[1]
    if not len(U):
        return np.r_[np.zeros(k), 1.0]
    At = np.column_stack([A, U])
    Zt = np.column_stack([Zm, np.ones(len(U))])

    def f(theta):
        p = np.exp(theta - theta.max())
        p /= p.sum()
        num, den = At @ p, Zt @ p
        val = -(np.log(np.maximum(num, 1e-300)) - np.log(den)).sum()
        g = -p * ((At / np.maximum(num, 1e-300)[:, None]) - (Zt / den[:, None])).sum(0)
        return val, g
    r = minimize(f, np.zeros(k + 1), jac=True, method='L-BFGS-B', options=dict(maxiter=iters))
    p = np.exp(r.x - r.x.max())
    return p / p.sum()


def table_prog(prog, K):
    """Нуль-Т: таблица K самых частых «прочих» смещений (порядок q программы — по убыванию частоты) и остаток."""
    q = dict(list(prog['q'].items())[:K])
    out = dict(prog)
    out.update(q=q, q_rest=1 - sum(q.values()) if prog.get('n_other') else 1.0)
    return out


def op_coverage(items, offs, prog, ops):
    """Доля «прочих» ответов головы, которые объясняет каждый оператор (для правила каталога)."""
    A, _, _ = other_rows(items, offs, prog, ops)
    if not len(A):
        return {op: 0.0 for op in ops}
    return {op: float((A[:, j] > 0).mean()) for j, op in enumerate(ops)}


def select_catalog(cov):
    """cov: {семейство: {голова: {оператор: доля}}} на построении → каталог по правилу CATALOG_MIN (порядок CANDIDATE_OPS)."""
    return [op for op in CANDIDATE_OPS if any(c.get(op, 0.0) >= CATALOG_MIN for fam in cov.values() for c in fam.values())]


def fit_head(items, offs, ops):
    """Программа головы DISTILL-02 и всё, что к ней добавляет DISTILL-04: веса операторов (М), нуль-Т того же размера, М+Т."""
    prog = D2.fit_program(items, offs)
    A, Zm, U = other_rows(items, offs, prog, ops)
    pi = fit_weights(A, Zm, U)
    K = len(ops)
    # М+Т (описательно): операторы и таблица из TABLE_FULL − K смещений — веса совместно, тем же способом
    tq = list(prog['q'])[:max(TABLE_FULL - K, 0)]
    A2, Z2 = mt_rows(items, offs, prog, ops, tq)
    pi_mt = fit_weights(A2, Z2, U)
    return dict(prog=prog, ops=list(ops), pi=pi, prog_T=table_prog(prog, K), mt_offsets=tq, pi_mt=pi_mt, n_other=int(len(U)))


def mt_rows(items, offs, prog, ops, tq):
    """Строки М+Т: столбцы операторов, затем смещений таблицы (кандидат таблицы — y = s + d, если y ≥ 0 и не в опоре)."""
    A, Zm = [], []
    for it, d in zip(items, offs):
        if d >= NC or d == 0:
            continue
        S = support(prog, it)
        y = it['sum'] + int(d)
        if y in S:
            continue
        cand = candidates(it['a'], it['b'])
        ra, rz = [], []
        for op in ops:
            ck = cand[op] - S
            rz.append(1.0 if ck else 0.0)
            ra.append(1.0 / len(ck) if y in ck else 0.0)
        for dd in tq:
            yy = it['sum'] + int(dd)
            ok = yy >= 0 and yy not in S
            rz.append(1.0 if ok else 0.0)
            ra.append(1.0 if ok and yy == y else 0.0)
        A.append(ra)
        Zm.append(rz)
    k = len(ops) + len(tq)
    return np.array(A, float).reshape(-1, k), np.array(Zm, float).reshape(-1, k)


def q_m(fm, it, y, S, cand=None, mt=False):
    """Q_М(y) (или Q_М+Т) для y вне опоры S."""
    cand = candidates(it['a'], it['b']) if cand is None else cand
    pi = fm['pi_mt'] if mt else fm['pi']
    num, Z = 0.0, pi[-1]
    for k, op in enumerate(fm['ops']):
        ck = cand[op] - S
        if ck:
            Z += pi[k]
            if y in ck:
                num += pi[k] / len(ck)
    if mt:
        K = len(fm['ops'])
        for j, dd in enumerate(fm['mt_offsets']):
            yy = it['sum'] + int(dd)
            if yy >= 0 and yy not in S:
                Z += pi[K + j]
                if yy == y:
                    num += pi[K + j]
    num += pi[-1] / D2.ref_size(it['sum'])
    return num / Z


def answer_probs(fm, it, y):
    """Вероятности ответа y у четырёх программ: М, нуль-Т, таблица DISTILL-02 (30), М+Т. Часть переноса у всех одна."""
    dist = D2.program_dist(fm['prog'], it, True)
    if y in dist:
        p = dist[y]
        return dict(M=p, T=p, T30=p, MT=p)
    S = set(dist)
    eps = fm['prog']['eps']
    cand = candidates(it['a'], it['b'])
    return dict(M=eps * q_m(fm, it, y, S, cand), T=D2.answer_prob(fm['prog_T'], it, y, True, dist),
                T30=D2.answer_prob(fm['prog'], it, y, True, dist), MT=eps * q_m(fm, it, y, S, cand, mt=True))


def top3_wrong(fm, it, kind):
    """Три самых вероятных неверных ответа программы kind ('M' или 'T') на задаче: опора переноса без верного ответа и кандидаты
    «прочих» (операторы или смещения таблицы); равномерный остаток в верх не попадает."""
    dist = D2.program_dist(fm['prog'], it, True)
    S = set(dist)
    s = it['sum']
    pr = {y: p for y, p in dist.items() if y != s}
    eps = fm['prog']['eps']
    if kind == 'M':
        cand = candidates(it['a'], it['b'])
        ys = set().union(*[cand[op] - S for op in fm['ops']]) if fm['ops'] else set()
        for y in ys:
            pr[y] = eps * q_m(fm, it, y, S, cand)
    else:
        for dd in fm['prog_T']['q']:
            y = s + int(dd)
            if y >= 0 and y not in S:
                pr[y] = D2.answer_prob(fm['prog_T'], it, y, True, dist)
    return [y for y, _ in sorted(pr.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]


# ───────────── заглушки и выборка ответов по программе-М (контроли совета 77)
def sample_m(fm, it, rng):
    """Один ответ (смещение) по программе-М: часть переноса — как distill02.program_dist; «прочее» — оператор по весам, кандидат
    равновероятно; остаток — случайное число с тем же числом цифр, что верная сумма (вне опоры)."""
    dist = D2.program_dist(fm['prog'], it, True)
    u, acc = rng.random(), 0.0
    for y, p in dist.items():
        acc += p
        if u < acc:
            return y - it['sum']
    S = set(dist)
    cand = candidates(it['a'], it['b'])
    pi = fm['pi']
    live = [(k, sorted(cand[op] - S)) for k, op in enumerate(fm['ops'])]
    w = np.array([pi[k] if ck else 0.0 for k, ck in live] + [pi[-1]])
    j = rng.choice(len(w), p=w / w.sum())
    if j < len(live):
        ck = live[j][1]
        return int(ck[rng.integers(len(ck))]) - it['sum']
    n = len(str(it['sum']))
    while True:
        y = int(rng.integers(10 ** (n - 1), 10 ** n))
        if y not in S:
            return y - it['sum']


# ───────────── меры по средам
def env_rows(fits, env_items, env_offs, heads):
    """По задачам × головам: лог-вероятности (смесь λ) четырёх программ, метки «неверный», «прочий», попадание в три самых вероятных
    неверных ответа у М и у нуля-Т. NaN — нечисловой ответ или голова вне среды."""
    n, H = len(env_items), len(heads)
    L = {k: np.full((n, H), np.nan) for k in ('M', 'T', 'T30', 'MT')}
    wrong = np.zeros((n, H), bool)
    other = np.zeros((n, H), bool)
    hitM = np.zeros((n, H), bool)
    hitT = np.zeros((n, H), bool)
    V = np.array([D2.ref_size(it['sum']) for it in env_items], float)
    for h_i, h in enumerate(heads):
        fm = fits[h]
        o = env_offs[h]
        for i, (it, d) in enumerate(zip(env_items, o)):
            if d >= NC:
                continue
            y = it['sum'] + int(d)
            pr = answer_probs(fm, it, y)
            for k in L:
                L[k][i, h_i] = float(D2.mixed_log(pr[k], V[i]))
            if d != 0:
                wrong[i, h_i] = True
                S = support(fm['prog'], it)
                other[i, h_i] = y not in S
                hitM[i, h_i] = y in top3_wrong(fm, it, 'M')
                hitT[i, h_i] = y in top3_wrong(fm, it, 'T')
    return dict(L=L, wrong=wrong, other=other, hitM=hitM, hitT=hitT, n=n, heads=list(heads))


def measures_w(er, Wm):
    """Меры среды при весах задач Wm (строки — точка или повторы бутстрепа):
      m_M   — среднее по головам разности М − нуль-Т на числовой ответ (решающая П1);
      m_Mo  — то же по «прочим» ответам (описательно);
      top3  — среднее по головам (доля неверных, названных М среди трёх) − (то же у нуля-Т) (П2);
      m_T30 — М − таблица DISTILL-02 (30), m_MT — М+Т − таблица (30) (описательно)."""
    num = np.isfinite(er['L']['M']).astype(float)
    cnt = Wm @ num

    def hm(x, y, mask):
        m = mask.astype(float)
        with np.errstate(invalid='ignore', divide='ignore'):
            return (Wm @ np.where(m > 0, np.nan_to_num(er['L'][x] - er['L'][y]), 0.0)) / (Wm @ m)
    with np.errstate(invalid='ignore', divide='ignore'):
        mM = hm('M', 'T', num > 0)
        mMo = hm('M', 'T', er['other'])
        mT30 = hm('M', 'T30', num > 0)
        mMT = hm('MT', 'T30', num > 0)
        wr = er['wrong'].astype(float)
        top = (Wm @ (er['hitM'] & er['wrong']).astype(float) - Wm @ (er['hitT'] & er['wrong']).astype(float)) / (Wm @ wr)
    return dict(m_M=np.nanmean(mM, 1), m_Mo=np.nanmean(mMo, 1), top3=np.nanmean(top, 1), m_T30=np.nanmean(mT30, 1), m_MT=np.nanmean(mMT, 1))


MEASURES = ('m_M', 'm_Mo', 'top3', 'm_T30', 'm_MT')


def env_measures(er, B, rng):
    """Точка и B повторов бутстрепа по задачам (строки с возвращением, одни и те же для всех голов)."""
    n = er['n']
    pt = {k: float(v[0]) for k, v in measures_w(er, np.ones((1, n))).items()}
    reps = {k: np.full(B, np.nan) for k in MEASURES}
    IDX = rng.integers(0, n, (B, n))
    for s in range(0, B, 500):
        Wb = np.stack([np.bincount(r, minlength=n) for r in IDX[s:s + 500]]).astype(float)
        for k, v in measures_w(er, Wb).items():
            reps[k][s:s + 500] = v
    sd = {k: (float(np.nanstd(v, ddof=1)) if np.isfinite(v).sum() > 1 else float('nan')) for k, v in reps.items()}
    return pt, sd, reps


def fit_family(items, offs, ops):
    return {h: fit_head(items, o, ops) for h, o in sorted(offs.items())}


def coverage_family(items, offs):
    """Доли операторов-кандидатов по головам семейства на построении (для правила каталога)."""
    out = {}
    for h, o in sorted(offs.items()):
        prog = D2.fit_program(items, o)
        out[h] = op_coverage(items, o, prog, list(CANDIDATE_OPS))
    return out
