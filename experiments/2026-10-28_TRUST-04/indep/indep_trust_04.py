#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRUST-04, блок В: независимая реализация эволюционной модели по indep/SPEC.md.

Написано только по тексту SPEC.md (лежит рядом с этим файлом). Код и результаты опытов
TRUST-01…04 не открывались и не импортируются. Зависимости: Python 3, numpy, scipy.

Режимы (SPEC §6):
  --theory    печатает w_my, b*, w_far и их лог-потери -> indep/theory/results_indep_04.json
  --pilot     зёрна 1200–1204, все 4 руки               -> indep/pilot/results_indep_04.json
  --test      зёрна 600–609, все 4 руки                 -> indep/test/results_indep_04.json
  --selftest  проверки кода вторым способом (зерно 4242; тестовые и пилотные зёрна не трогает)

Ключ --noise {sd,var} — как читать N(0; 0,01) и N(0; 0,04) из SPEC §3 (текст неоднозначен):
  sd  (по умолчанию) — второе число есть стандартное отклонение (как scale у numpy.normal);
  var — второе число есть дисперсия (СКО 0,1 и 0,2). Результаты с var пишутся в <режим>_noisevar/.

Порядок случайных чисел (SPEC §6 оставляет его на усмотрение):
  старт: w0 (m×n), затем w4 (m×n; у COUNCIL — m генов групп);
  поколение: U(40×9) эпизодов [W, x1, x2, x3, x5, h4, решение пересказа, независимый ответ
  ист. 6, u] -> m равномерных для отбора групп (только при m > 1) -> m×n равномерных для отбора
  внутри групп -> N(0, ·) мутации w0 (m×n) -> N(0, ·) мутации w4 (m×n; у COUNCIL — m).
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from itertools import product

import numpy as np
import scipy
from scipy import optimize, special, stats

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- мир (SPEC §1)
PI_W1 = 0.3                                    # P(W = 1)
R_HONEST = {1: 0.55, 2: 0.65, 3: 0.75, 5: 0.92}  # честные независимые источники
R_G = 0.85                                     # надёжность источника 4 («с интересом»)
C_RETELL = 0.8                                 # источник 6 повторяет x3 с этой вероятностью
R6_IND = 0.75                                  # надёжность независимого ответа источника 6
B_MAX = 0.6
W_REF = math.log(R_G / (1.0 - R_G))            # logit(r_G)

# ---------------------------------------------------------------- популяция (SPEC §3, §4)
N_GEN = 3000
L_EP = 40
ARMS = ("MYOPIC", "DEMES", "POOLED", "COUNCIL")
ARM_ID = {"MYOPIC": 0, "DEMES": 1, "POOLED": 2, "COUNCIL": 3}
ARM_SHAPE = {"MYOPIC": (1, 400), "DEMES": (40, 10), "POOLED": (40, 10), "COUNCIL": (40, 10)}
NOISE = {  # (СКО старта, СКО мутации)
    "sd": (0.01, 0.04),
    "var": (math.sqrt(0.01), math.sqrt(0.04)),
}
SNAP_EVERY = 10
BURN = 1000
SEEDS = {"pilot": list(range(1200, 1205)), "test": list(range(600, 610))}


def logit(p):
    return math.log(p / (1.0 - p))


# ---------------------------------------------------------------- агент (SPEC §2)
def pair_L(r, c):
    """L = ln[ r(c + (1−c)r) / ((1−r)(c + (1−c)(1−r))) ] — вклад пары (x3, x6) при x3 = x6 = +1."""
    return math.log(r * (c + (1 - c) * r) / ((1 - r) * (c + (1 - c) * (1 - r))))


L36 = pair_L(R_HONEST[3], C_RETELL)
W_FIXED = {1: logit(R_HONEST[1]), 2: logit(R_HONEST[2]), 3: L36 / 2,
           5: logit(R_HONEST[5]), 6: L36 / 2}


def l_plus_minus(b):
    lp = math.log(R_G / ((1 - R_G) + R_G * b))
    lm = math.log((1 - R_G) / (R_G * (1 - b)))
    return lp, lm


def w4_bayes(b):
    lp, lm = l_plus_minus(b)
    return 0.5 * (lp - lm)


def w0_bayes(b):
    lp, lm = l_plus_minus(b)
    return logit(PI_W1) + 0.5 * (lp + lm)


def b_of_w4(w4, b_max=B_MAX):
    """Доля лжи b = B_MAX·clip(w̄4 / W_REF, 0, 1); работает со скалярами и массивами."""
    return b_max * np.clip(np.asarray(w4, dtype=float) / W_REF, 0.0, 1.0)


# ---------------------------------------------------------------- точная таблица (SPEC §4)
def build_other_table():
    """Совместные вероятности W и сигналов всех источников, кроме 4-го (32 сочетания),
    получены прямо из порождающего механизма (а не из формулы для L), и постоянная часть z."""
    pats = np.array(list(product((-1.0, 1.0), repeat=5)))  # столбцы: x1, x2, x3, x5, x6
    x1, x2, x3, x5, x6 = pats.T
    Q = np.zeros((2, pats.shape[0]))
    for W in (0, 1):
        s = 2 * W - 1
        p = np.full(pats.shape[0], PI_W1 if W == 1 else 1.0 - PI_W1)
        for col, r in ((x1, R_HONEST[1]), (x2, R_HONEST[2]), (x5, R_HONEST[5])):
            p = p * np.where(col == s, r, 1.0 - r)
        p3 = np.where(x3 == s, R_HONEST[3], 1.0 - R_HONEST[3])
        p6 = C_RETELL * (x6 == x3) + (1.0 - C_RETELL) * np.where(x6 == s, R6_IND, 1.0 - R6_IND)
        Q[W] = p * p3 * p6
    cvec = (W_FIXED[1] * x1 + W_FIXED[2] * x2 + W_FIXED[3] * x3
            + W_FIXED[5] * x5 + W_FIXED[6] * x6)
    return pats, Q, cvec


PATS, QTAB, CVEC = build_other_table()


def softplus(t):
    return np.logaddexp(0.0, t)


def exact_loss(w0, w4, b):
    """Точная ожидаемая лог-потеря за эпизод (наты): −Σ P(W, x)·ln P_агента(W | x)
    по всем 2×64 сочетаниям в мире с долей лжи b. Аргументы — скаляры или массивы формы (G,)."""
    w0 = np.atleast_1d(np.asarray(w0, dtype=float))
    w4 = np.atleast_1d(np.asarray(w4, dtype=float))
    b = np.atleast_1d(np.asarray(b, dtype=float))
    zp = w0[:, None] + w4[:, None] + CVEC[None, :]   # x4 = +1
    zm = w0[:, None] - w4[:, None] + CVEC[None, :]   # x4 = −1
    p0p = ((1.0 - R_G) + R_G * b)[:, None]           # P(x4 = +1 | W = 0)
    # W = 1: −ln σ(z) = softplus(−z);  W = 0: −ln(1 − σ(z)) = softplus(z)
    l1 = QTAB[1][None, :] * (R_G * softplus(-zp) + (1.0 - R_G) * softplus(-zm))
    l0 = QTAB[0][None, :] * (p0p * softplus(zp) + (1.0 - p0p) * softplus(zm))
    return (l1 + l0).sum(axis=1)


def full_joint(b):
    """P(W, x1..x6) прямым перебором порождающего механизма, включая h4 и ложь (для проверок)."""
    P = np.zeros((2, 64))
    xs = list(product((-1, 1), repeat=6))
    for W in (0, 1):
        s = 2 * W - 1
        pW = PI_W1 if W == 1 else 1.0 - PI_W1
        for j, x in enumerate(xs):
            x1, x2, x3, x4, x5, x6 = x
            p = pW
            for xi, r in ((x1, R_HONEST[1]), (x2, R_HONEST[2]), (x3, R_HONEST[3]), (x5, R_HONEST[5])):
                p *= r if xi == s else 1.0 - r
            p4 = 0.0
            for h4, ph in ((s, R_G), (-s, 1.0 - R_G)):
                if W == 0 and h4 == -1:
                    p4 += ph * (b if x4 == 1 else 1.0 - b)
                else:
                    p4 += ph * (1.0 if x4 == h4 else 0.0)
            p6 = C_RETELL * (1.0 if x6 == x3 else 0.0) + (1.0 - C_RETELL) * (R6_IND if x6 == s else 1.0 - R6_IND)
            P[W, j] = p * p4 * p6
    return np.array(xs, dtype=float), P


# ---------------------------------------------------------------- теория (SPEC §5)
def min_over_w0(w4, b, w0_start=None, tol=1e-14, max_iter=200):
    """min по w0 точной лог-потери при данных w4 и b (функция выпукла по w0; метод Ньютона)."""
    w0 = w0_bayes(b) if w0_start is None else float(w0_start)
    p0p = (1.0 - R_G) + R_G * b
    for _ in range(max_iter):
        sp = special.expit(w0 + w4 + CVEC)
        sm = special.expit(w0 - w4 + CVEC)
        grad = (QTAB[1] * (R_G * (sp - 1.0) + (1.0 - R_G) * (sm - 1.0))).sum() \
            + (QTAB[0] * (p0p * sp + (1.0 - p0p) * sm)).sum()
        hess = ((QTAB[1] * R_G + QTAB[0] * p0p) * sp * (1.0 - sp)).sum() \
            + ((QTAB[1] * (1.0 - R_G) + QTAB[0] * (1.0 - p0p)) * sm * (1.0 - sm)).sum()
        step = grad / hess
        w0 -= step
        if abs(step) < tol:
            break
    return w0, float(exact_loss(w0, w4, b)[0])


def far_objective(w4):
    """min по w0 точной лог-потери в мире, где b задаётся самим w4."""
    b = float(b_of_w4(w4))
    return min_over_w0(float(w4), b)[1]


def theory():
    # близорукая точка: бисекция f(b) = B_MAX·clip(w4ᴮ(b)/W_REF) − b на [0, B_MAX]
    def f(b):
        return float(b_of_w4(w4_bayes(b))) - b

    lo, hi = 0.0, B_MAX
    assert f(lo) > 0 > f(hi)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-16:
            break
    b_star = 0.5 * (lo + hi)
    b_star_brentq = optimize.brentq(f, 0.0, B_MAX, xtol=1e-15, rtol=1e-15)
    w_my = w4_bayes(b_star)
    w0_my_num, loss_my = min_over_w0(w_my, b_star)

    # дальновидная точка: сетка шире [0, W_REF], затем уточнение ограниченным методом Брента
    grid = np.linspace(-1.0, W_REF + 1.0, 4001)
    vals = np.array([far_objective(w) for w in grid])
    i = int(np.argmin(vals))
    lo_g, hi_g = grid[max(i - 2, 0)], grid[min(i + 2, grid.size - 1)]
    res = optimize.minimize_scalar(far_objective, bounds=(lo_g, hi_g), method="bounded",
                                   options={"xatol": 1e-12, "maxiter": 500})
    w_far = float(res.x)
    b_far = float(b_of_w4(w_far))
    w0_far, loss_far = min_over_w0(w_far, b_far)
    h = 1e-5
    dg = (far_objective(w_far + h) - far_objective(w_far - h)) / (2 * h)
    d2g = (far_objective(w_far + h) - 2 * far_objective(w_far) + far_objective(w_far - h)) / h ** 2
    # локальные минимумы на сетке (проверка единственности)
    loc_min = [float(grid[k]) for k in range(1, grid.size - 1)
               if vals[k] < vals[k - 1] and vals[k] <= vals[k + 1]]

    honest_w0, honest_loss = min_over_w0(W_REF, 0.0)
    no4_w0, no4_loss_at_bstar = min_over_w0(0.0, b_star)
    return {
        "constants": {
            "pi": PI_W1, "r_honest": {str(k): v for k, v in R_HONEST.items()}, "r_G": R_G,
            "c_retell": C_RETELL, "r6_independent": R6_IND, "B_MAX": B_MAX, "W_REF": W_REF,
            "L36": L36, "w_fixed": {f"w{k}": v for k, v in W_FIXED.items()},
        },
        "b_star": b_star,
        "b_star_brentq_check": b_star_brentq,
        "w_my": w_my,
        "w0_my": w0_bayes(b_star),
        "w0_my_numeric_check": w0_my_num,
        "loss_my": loss_my,
        "w_far": w_far,
        "b_far": b_far,
        "w0_far": w0_far,
        "loss_far": loss_far,
        "far_grid_argmin": float(grid[i]),
        "far_grid_local_minima": loc_min,
        "far_dg_dw4_at_w_far": dg,
        "far_d2g_dw4_2_at_w_far": d2g,
        "far_objective_at_w_my": far_objective(w_my),
        "loss_gap_my_minus_far": loss_my - loss_far,
        "reference": {
            "honest_world_bayes": {"w4": W_REF, "w0": honest_w0, "loss": honest_loss},
            "ignore_source4_at_b_star": {"w4": 0.0, "w0": no4_w0, "loss": no4_loss_at_bstar},
            "far_objective_at_w4_0": far_objective(0.0),
            "far_objective_at_W_REF": far_objective(W_REF),
        },
    }


# ---------------------------------------------------------------- симуляция (SPEC §3)
def draw_episodes(rng, L):
    """L эпизодов, общих для всех групп поколения (SPEC §3 п. 2). Одна матрица U ~ U[0,1)
    формы (L, 9); столбцы: W, x1, x2, x3, x5, h4, решение пересказа, независимый ответ ист. 6, u."""
    U = rng.random((L, 9))
    W = U[:, 0] < PI_W1
    s = np.where(W, 1.0, -1.0)
    x1 = np.where(U[:, 1] < R_HONEST[1], s, -s)
    x2 = np.where(U[:, 2] < R_HONEST[2], s, -s)
    x3 = np.where(U[:, 3] < R_HONEST[3], s, -s)
    x5 = np.where(U[:, 4] < R_HONEST[5], s, -s)
    h4 = np.where(U[:, 5] < R_G, s, -s)
    retell = U[:, 6] < C_RETELL
    x6 = np.where(retell, x3, np.where(U[:, 7] < R6_IND, s, -s))
    u = U[:, 8]
    cconst = (W_FIXED[1] * x1 + W_FIXED[2] * x2 + W_FIXED[3] * x3
              + W_FIXED[5] * x5 + W_FIXED[6] * x6)
    return {"W": W, "s": s, "x1": x1, "x2": x2, "x3": x3, "x5": x5, "x6": x6,
            "h4": h4, "u": u, "liable": (~W) & (h4 < 0), "cconst": cconst}


def x4_for_groups(ep, b):
    """x4 группы k: +1, если W = 0, h4 = −1 и u < b_k; иначе h4. Форма (m, L)."""
    lie = ep["liable"][None, :] & (ep["u"][None, :] < np.asarray(b)[:, None])
    return np.where(lie, 1.0, ep["h4"][None, :])


def log_payoff(w0, w4act, ep, x4):
    """ln F = Σ по эпизодам ln P(истины) = Σ ln σ(s·z); w0, w4act — (m, n), x4 — (m, L)."""
    z = w0[:, :, None] + ep["cconst"][None, None, :] + w4act[:, :, None] * x4[:, None, :]
    return -np.logaddexp(0.0, -ep["s"][None, None, :] * z).sum(axis=2)


def pick(cum, U):
    """Индексы с вероятностью ∝ весу: cum — накопленные веса (cum[-1] > 0), U ∈ [0, 1)."""
    total = cum[-1]
    v = np.minimum(U * total, np.nextafter(total, 0.0))
    return np.searchsorted(cum, v, side="right")


def run_arm(seed, arm, noise="sd", n_gen=N_GEN, b_max=B_MAX, rng_seed=None):
    sd0, sdm = NOISE[noise]
    m, n = ARM_SHAPE[arm]
    council = arm == "COUNCIL"
    rng = np.random.default_rng(seed * 100 + ARM_ID[arm] if rng_seed is None else rng_seed)
    t_wall, t_cpu = time.perf_counter(), time.process_time()

    w0 = rng.normal(0.0, sd0, size=(m, n))
    w4 = rng.normal(0.0, sd0, size=m) if council else rng.normal(0.0, sd0, size=(m, n))

    snaps = []
    for g in range(n_gen):
        # 1. средний вес на источнике 4 и доля лжи по группам
        wbar4 = w4 if council else w4.mean(axis=1)
        b = b_max * np.clip(wbar4 / W_REF, 0.0, 1.0)
        # 2. эпизоды, общие для всех групп; x4 зависит от b_k
        ep = draw_episodes(rng, L_EP)
        x4 = x4_for_groups(ep, b)
        # 3. выплата с тем весом, с которым особь действует
        if arm in ("MYOPIC", "DEMES"):
            w4act = w4
        elif arm == "POOLED":
            w4act = np.repeat(wbar4[:, None], n, axis=1)
        else:  # COUNCIL
            w4act = np.repeat(w4[:, None], n, axis=1)
        logF = log_payoff(w0, w4act, ep, x4)
        gmax = logF.max(axis=1, keepdims=True)
        Frel = np.exp(logF - gmax)                        # F / max_группы, без потери точности
        # 4. отбор групп ∝ среднему арифметическому F по особям группы
        if m > 1:
            log_gfit = gmax[:, 0] + np.log(Frel.mean(axis=1))
            parents = pick(np.cumsum(np.exp(log_gfit - log_gfit.max())), rng.random(m))
        else:
            parents = np.zeros(1, dtype=np.int64)
        # 5. отбор внутри группы ∝ F, с возвращением; оба гена от одного родителя
        U2 = rng.random((m, n))
        cum = np.cumsum(Frel, axis=1)
        idx = np.empty((m, n), dtype=np.int64)
        for k in range(m):
            idx[k] = pick(cum[parents[k]], U2[k])
        new_w0 = w0[parents[:, None], idx]
        new_w4 = w4[parents] if council else w4[parents[:, None], idx]
        w0 = new_w0 + rng.normal(0.0, sdm, size=new_w0.shape)
        w4 = new_w4 + rng.normal(0.0, sdm, size=new_w4.shape)

        # снимок — после размножения и мутации (SPEC §4)
        if g % SNAP_EVERY == 0 or g == n_gen - 1:
            w0bar = w0.mean(axis=1)
            w4bar = w4 if council else w4.mean(axis=1)
            bk = b_max * np.clip(w4bar / W_REF, 0.0, 1.0)
            lossk = exact_loss(w0bar, w4bar, bk)
            within = 0.0 if council else float(w4.std(axis=1).mean())
            snaps.append((g, float(w4bar.mean()), float(lossk.mean()), float(w0bar.mean()),
                          float(bk.mean()), float(w4bar.std()), within))

    snaps = np.array(snaps)
    sel = snaps[:, 0] >= BURN
    n_sel = int(sel.sum())
    first = sel & (snaps[:, 0] < 2000)
    second = snaps[:, 0] >= 2000
    out = {
        "w_G": float(snaps[sel, 1].mean()),
        "loss": float(snaps[sel, 2].mean()),
        "w0_mean": float(snaps[sel, 3].mean()),
        "b_mean": float(snaps[sel, 4].mean()),
        "between_group_sd_w4": float(snaps[sel, 5].mean()),
        "within_group_sd_w4": float(snaps[sel, 6].mean()),
        "w_G_g1000_1999": float(snaps[first, 1].mean()) if first.any() else float("nan"),
        "w_G_g2000_2999": float(snaps[second, 1].mean()) if second.any() else float("nan"),
        "n_snapshots_used": n_sel,
        "time_wall_s": time.perf_counter() - t_wall,
        "time_cpu_s": time.process_time() - t_cpu,
    }
    traj = {"g": snaps[:, 0].astype(int).tolist(), "w4": snaps[:, 1].tolist(),
            "loss": snaps[:, 2].tolist(), "w0": snaps[:, 3].tolist(), "b": snaps[:, 4].tolist(),
            "between_sd_w4": snaps[:, 5].tolist(), "within_sd_w4": snaps[:, 6].tolist()}
    return out, traj


# ---------------------------------------------------------------- служебное
def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


INTERPRETATION = [
    "N(0; a) из SPEC §3: при --noise sd второе число — СКО (старт 0,01, мутация 0,04); при --noise var — дисперсия (СКО 0,1 и 0,2).",
    "Лог-потеря точек теории: min по w0 точной лог-потери в своём мире (у w_my он совпадает с w0ᴮ(b*), проверено численно).",
    "w_far: поиск по сетке w4 ∈ [−1; W_REF + 1] (4001 узел), затем ограниченный метод Брента вокруг лучшего узла.",
    "Средний F группы считается как ln(среднего) через вычитание максимума; при равных весах выбор — searchsorted(side='right').",
    "Независимый ответ источника 6 разыгрывается в каждом эпизоде (используется только без пересказа).",
    "MYOPIC: одна группа из 400, b — по среднему w4 всей популяции; родитель новой группы — сама группа.",
    "POOLED: действующий вес — среднее w4 группы в начале поколения (то же, по которому считается b_k).",
    "COUNCIL: ген w4 мутирует один раз на новую группу; w0 — у каждой особи свой.",
    "Снимок: средний генотип группы после размножения и мутации поколения g; b_k — по этому среднему.",
    "u = (w_G − w_far)/(w_my − w_far) по каждому зерну; среднее u по зёрнам равно u от среднего w_G.",
]


def meta(noise):
    return {
        "script": os.path.abspath(__file__),
        "script_sha256": sha256_of(os.path.abspath(__file__)),
        "spec_sha256": sha256_of(os.path.join(HERE, "SPEC.md")),
        "python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__,
        "platform": platform.platform(),
        "noise_convention": noise,
        "sd_init": NOISE[noise][0], "sd_mut": NOISE[noise][1],
        "n_gen": N_GEN, "episodes": L_EP, "burn_in": BURN, "snap_every": SNAP_EVERY,
        "rng": "numpy.random.default_rng(seed*100 + arm_id); MYOPIC 0, DEMES 1, POOLED 2, COUNCIL 3",
        "interpretation": INTERPRETATION,
        "started": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }


def out_dir(mode, noise):
    d = os.path.join(HERE, mode if noise == "sd" else f"{mode}_noisevar")
    os.makedirs(d, exist_ok=True)
    return d


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def print_theory(th):
    print(f"W_REF = {th['constants']['W_REF']:.10f}   L36/2 = {th['constants']['L36'] / 2:.10f}")
    print(f"b*    = {th['b_star']:.10f}   (brentq: {th['b_star_brentq_check']:.10f})")
    print(f"w_my  = {th['w_my']:.10f}   w0_my = {th['w0_my']:.10f}   лог-потеря = {th['loss_my']:.10f}")
    print(f"w_far = {th['w_far']:.10f}   w0_far = {th['w0_far']:.10f}   b_far = {th['b_far']:.10f}"
          f"   лог-потеря = {th['loss_far']:.10f}")
    print(f"разница потерь (my − far) = {th['loss_gap_my_minus_far']:.3e};"
          f"  dg/dw4 в w_far = {th['far_dg_dw4_at_w_far']:.2e};"
          f"  локальные минимумы сетки: {th['far_grid_local_minima']}")


# ---------------------------------------------------------------- режимы
def mode_theory(noise):
    th = theory()
    print_theory(th)
    path = os.path.join(out_dir("theory", noise), "results_indep_04.json")
    write_json(path, {"meta": meta(noise), "theory": th})
    print(f"записано: {path}")
    return th


def summarize(runs, th):
    summary = {}
    for arm in ARMS:
        rs = [r for r in runs if r["arm"] == arm]
        if not rs:
            continue
        wg = np.array([r["w_G"] for r in rs])
        uu = np.array([r["u"] for r in rs])
        lo = np.array([r["loss"] for r in rs])
        k = len(rs)
        tq = float(stats.t.ppf(0.975, k - 1)) if k > 1 else float("nan")
        se_u = float(uu.std(ddof=1) / math.sqrt(k)) if k > 1 else float("nan")
        summary[arm] = {
            "n_seeds": k,
            "w_G_mean": float(wg.mean()), "w_G_sd": float(wg.std(ddof=1)) if k > 1 else float("nan"),
            "u_mean": float(uu.mean()), "u_sd": float(uu.std(ddof=1)) if k > 1 else float("nan"),
            "u_ci95": [float(uu.mean() - tq * se_u), float(uu.mean() + tq * se_u)],
            "loss_mean": float(lo.mean()),
            "time_wall_s_total": float(sum(r["time_wall_s"] for r in rs)),
        }
    return summary


def mode_runs(mode, noise):
    th = theory()
    print_theory(th)
    seeds = SEEDS[mode]
    d = out_dir(mode, noise)
    path = os.path.join(d, "results_indep_04.json")
    tpath = os.path.join(d, "traj_indep_04.json")
    m = meta(noise)
    m["seeds"] = seeds
    runs, trajs = [], {}
    t_all = time.perf_counter()
    for seed in seeds:
        for arm in ARMS:
            res, traj = run_arm(seed, arm, noise=noise)
            res["u"] = (res["w_G"] - th["w_far"]) / (th["w_my"] - th["w_far"])
            res.update({"seed": seed, "arm": arm, "rng_seed": seed * 100 + ARM_ID[arm]})
            runs.append(res)
            trajs[f"{seed}_{arm}"] = traj
            print(f"[{mode}/{noise}] зерно {seed} {arm:8s} w_G = {res['w_G']:.5f}  u = {res['u']:+.4f}"
                  f"  потеря = {res['loss']:.6f}  w0 = {res['w0_mean']:.4f}"
                  f"  ({res['time_wall_s']:.1f} с, ЦП {res['time_cpu_s']:.1f} с)", flush=True)
            partial = {"meta": m, "complete": False, "theory": th, "runs": runs,
                       "summary": summarize(runs, th)}
            write_json(path, partial)
    total = time.perf_counter() - t_all
    summary = summarize(runs, th)
    write_json(path, {"meta": m, "complete": True, "time_wall_s_total": total, "theory": th,
                      "runs": runs, "summary": summary})
    write_json(tpath, {"meta": {"note": "траектории снимков (g = 0, 10, …, 2990, 2999); средние по группам"},
                       "traj": trajs})
    print(f"всего {total:.1f} с; записано: {path}")
    for arm, s in summary.items():
        print(f"  {arm:8s} w_G = {s['w_G_mean']:.5f} ± {s['w_G_sd']:.5f}   u = {s['u_mean']:+.4f}"
              f"  [95 %: {s['u_ci95'][0]:+.4f}; {s['u_ci95'][1]:+.4f}]   потеря = {s['loss_mean']:.6f}")


def mode_selftest():
    """Проверки вторым способом. Зерно 4242 — вне тестовых (600–609) и пилотных (1200–1204)."""
    ok = True
    print("1. Таблица мира: сумма вероятностей, частные надёжности, формула L.")
    xs, P = None, None
    for b in (0.0, 0.25, 0.6):
        xs, P = full_joint(b)
        tot = P.sum()
        print(f"   b = {b}: Σ P = {tot:.15f}")
        ok &= abs(tot - 1) < 1e-12
    xs, P = full_joint(0.37)
    for W in (0, 1):
        s = 2 * W - 1
        pW = P[W].sum()
        for i, r in ((0, 0.55), (1, 0.65), (2, 0.75), (4, 0.92), (5, 0.75)):
            emp = P[W][xs[:, i] == s].sum() / pW
            ok &= abs(emp - r) < 1e-12
        p4p = P[W][xs[:, 3] == 1].sum() / pW
        want = R_G if W == 1 else (1 - R_G) + R_G * 0.37
        ok &= abs(p4p - want) < 1e-12
    print(f"   частные надёжности и P(x4=+1|W) совпали: {ok}")

    print("2. Байесовские веса SPEC против апостериорной вероятности из таблицы.")
    for b in (0.0, 0.2, 0.37, 0.6):
        xs, P = full_joint(b)
        post = P[1] / (P[0] + P[1])
        w = np.array([W_FIXED[1], W_FIXED[2], W_FIXED[3], w4_bayes(b), W_FIXED[5], W_FIXED[6]])
        z = w0_bayes(b) + xs @ w
        err = np.abs(special.expit(z) - post).max()
        H = -(P * np.log(np.stack([1 - post, post]))).sum()
        dl = abs(exact_loss(w0_bayes(b), w4_bayes(b), b)[0] - H)
        print(f"   b = {b}: max|σ(z) − P(W=1|x)| = {err:.2e};  |потеря − H(W|X)| = {dl:.2e}")
        ok &= err < 1e-12 and dl < 1e-12

    print("3. exact_loss против прямой суммы по 128 клеткам для случайных (w0, w4, b).")
    rng = np.random.default_rng(4242)
    worst = 0.0
    for _ in range(20):
        w0, w4, b = rng.normal(-0.8, 1.0), rng.normal(1.0, 1.0), rng.uniform(0, 0.6)
        xs, P = full_joint(b)
        w = np.array([W_FIXED[1], W_FIXED[2], W_FIXED[3], w4, W_FIXED[5], W_FIXED[6]])
        z = w0 + xs @ w
        direct = -(P[1] * np.log(special.expit(z)) + P[0] * np.log(special.expit(-z))).sum()
        worst = max(worst, abs(direct - exact_loss(w0, w4, b)[0]))
    print(f"   max расхождение = {worst:.2e}")
    ok &= worst < 1e-12

    print("4. Генератор эпизодов против точной таблицы (Монте-Карло, хи-квадрат по 128 клеткам).")
    b_test = np.array([0.0, 0.37])
    counts = np.zeros((2, 2, 64))
    pow2 = 2 ** np.arange(5, -1, -1)
    n_ep = 0
    for _ in range(100):
        ep = draw_episodes(rng, 20000)
        x4 = x4_for_groups(ep, b_test)
        for gi in range(2):
            X = np.stack([ep["x1"], ep["x2"], ep["x3"], x4[gi], ep["x5"], ep["x6"]], axis=1)
            cell = ((X > 0).astype(int) * pow2).sum(axis=1)
            np.add.at(counts[gi], (ep["W"].astype(int), cell), 1)
        n_ep += 20000
    for gi, b in enumerate(b_test):
        xs, P = full_joint(float(b))
        exp_ = (P * n_ep).ravel()
        obs = counts[gi].ravel()
        keep = exp_ > 0
        chi = stats.chisquare(obs[keep], exp_[keep])
        print(f"   b = {b}: эпизодов {n_ep}, хи-квадрат = {chi.statistic:.1f} при {keep.sum() - 1} ст. св.,"
              f" p = {chi.pvalue:.3f}; клеток с нулевой вероятностью и ненулевым счётом: "
              f"{int(obs[~keep].sum())}")
        ok &= chi.pvalue > 1e-4 and obs[~keep].sum() == 0

    print("5. ln F: векторный счёт против явных циклов.")
    for arm in ARMS:
        m, n = ARM_SHAPE[arm]
        m, n = min(m, 4), min(n, 7)
        w0 = rng.normal(-0.8, 0.5, size=(m, n))
        w4 = rng.normal(1.0, 0.5, size=(m, n))
        b = b_of_w4(w4.mean(axis=1))
        ep = draw_episodes(rng, L_EP)
        x4 = x4_for_groups(ep, b)
        if arm in ("MYOPIC", "DEMES"):
            w4act = w4
        else:
            w4act = np.repeat(w4.mean(axis=1)[:, None], n, axis=1)
        vec = log_payoff(w0, w4act, ep, x4)
        loop = np.zeros((m, n))
        for k in range(m):
            for i in range(n):
                tot = 0.0
                for j in range(L_EP):
                    lie = (not ep["W"][j]) and ep["h4"][j] < 0 and ep["u"][j] < b[k]
                    xx4 = 1.0 if lie else ep["h4"][j]
                    z = (w0[k, i] + W_FIXED[1] * ep["x1"][j] + W_FIXED[2] * ep["x2"][j]
                         + W_FIXED[3] * ep["x3"][j] + w4act[k, i] * xx4 + W_FIXED[5] * ep["x5"][j]
                         + W_FIXED[6] * ep["x6"][j])
                    p1 = 1.0 / (1.0 + math.exp(-z))
                    tot += math.log(p1) if ep["W"][j] else math.log(1.0 - p1)
                loop[k, i] = tot
        err = np.abs(vec - loop).max()
        print(f"   {arm}: max|разница| = {err:.2e}")
        ok &= err < 1e-9

    print("6. Выбор ∝ весу: частоты pick против весов (с нулевыми весами).")
    wts = np.array([0.0, 1.0, 0.0, 3.0, 2.0, 0.0])
    U = rng.random(600000)
    ids = pick(np.cumsum(wts), U)
    freq = np.bincount(ids, minlength=wts.size) / U.size
    print(f"   частоты {np.round(freq, 4).tolist()} при долях {np.round(wts / wts.sum(), 4).tolist()}")
    ok &= freq[wts == 0].sum() == 0 and np.abs(freq - wts / wts.sum()).max() < 0.005

    print("7. Механика отбора: честный мир (B_MAX = 0) — популяция должна прийти к байесовским"
          " весам w4 = W_REF, w0 = logit 0,3.")
    for arm in ("MYOPIC", "COUNCIL"):
        res, traj = run_arm(4242, arm, noise="sd", n_gen=2000, b_max=0.0, rng_seed=4242 * 100 + ARM_ID[arm])
        g = np.array(traj["g"])
        sel = g >= 1000
        w4m = float(np.mean(np.array(traj["w4"])[sel]))
        w0m = float(np.mean(np.array(traj["w0"])[sel]))
        print(f"   {arm}: w4 = {w4m:.4f} (цель {W_REF:.4f}),  w0 = {w0m:.4f} (цель {logit(PI_W1):.4f}),"
              f"  {res['time_wall_s']:.1f} с")
        ok &= abs(w4m - W_REF) < 0.15 and abs(w0m - logit(PI_W1)) < 0.15
    print("ИТОГ САМОПРОВЕРКИ:", "все проверки пройдены" if ok else "ЕСТЬ ПРОВАЛЫ")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--theory", action="store_true")
    g.add_argument("--pilot", action="store_true")
    g.add_argument("--test", action="store_true")
    g.add_argument("--selftest", action="store_true")
    ap.add_argument("--noise", choices=("sd", "var"), default="sd")
    a = ap.parse_args()
    if a.theory:
        mode_theory(a.noise)
    elif a.pilot:
        mode_runs("pilot", a.noise)
    elif a.test:
        mode_runs("test", a.noise)
    else:
        sys.exit(0 if mode_selftest() else 1)


if __name__ == "__main__":
    main()
