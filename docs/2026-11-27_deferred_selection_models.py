"""Модели к docs/2026-11-27_deferred_selection_models.md («Отсрочка отбора: модели и предсказания»).
Это проверка вывода формул вторым способом и расчёт чисел, а не опыт: стохастическая модель в разделе М3 —
та же модель, что и формула, только со случайностью. Входные числа из мира помечены [сн.] (сниппет) или [пам.] (по памяти).
Запуск: python3 docs/2026-11-27_deferred_selection_models.py — пишет docs/2026-11-27_deferred_selection_models.json."""
import json, math, os
import numpy as np

out = {}

# ───────────────────────── М1. Длина щита ─────────────────────────
# Ученик копит умение Q(tau) = (1 − exp(−tau/theta))^k, потом пользуется им. Каждый год ожидания стоит h = mu + r
# (риск не дожить + цена отсрочки). Максимум ln Q(tau) − h·tau:  tau* = theta · ln(1 + k / (h·theta)).
def tau_star(theta, k, h):
    return theta * math.log(1 + k / (h * theta))

def tau_numeric(theta, k, h):          # второй способ: прямой поиск максимума золотым сечением
    f = lambda t: k * math.log(1 - math.exp(-t / theta)) - h * t
    lo, hi = 1e-9, 200 * theta + 200 / h
    g = (math.sqrt(5) - 1) / 2
    c, d = hi - g * (hi - lo), lo + g * (hi - lo)
    for _ in range(400):
        if f(c) > f(d): hi, d = d, c; c = hi - g * (hi - lo)
        else: lo, c = c, d; d = lo + g * (hi - lo)
    return (lo + hi) / 2

rng = np.random.default_rng(1)
worst = 0.0
for _ in range(200):
    th, k, h = 10 ** rng.uniform(-1, 2), 10 ** rng.uniform(-0.5, 0.7), 10 ** rng.uniform(-3, 0)
    a, b = tau_star(th, k, h), tau_numeric(th, k, h)
    worst = max(worst, abs(a - b) / a)
out['M1_check_max_rel_error_200_random'] = float(f'{worst:.2e}')

def alphaM(y, k):                      # безразмерное произведение «возраст зрелости × риск»: tau*·h = y·ln(1 + k/y), y = h·theta
    return y * math.log(1 + k / y)
def share(y, k):                       # доля предельной «длины» (умения до возведения в степень k), набранная к зрелости
    return k / (k + y)
def y_from_alphaM(target, k):          # обратная задача: какая «опасность × объём учёбы» даёт наблюдаемое произведение
    lo, hi = 1e-9, 1e6
    for _ in range(300):
        mid = math.sqrt(lo * hi)
        lo, hi = (mid, hi) if alphaM(mid, k) < target else (lo, mid)
    return math.sqrt(lo * hi)

out['M1_invariants'] = {
    'fish_k3_y1.5': dict(alphaM=round(alphaM(1.5, 3), 3), length_share_at_maturity=round(share(1.5, 3), 3),
                         note='k = 3 (плодовитость ~ длина^3), y = M/K = 1,5; сравнить: Beverton–Holt/Jensen 1996 — 1,65 и 0,66 [пам.]'),
    'limit_y_to_infinity_k1': 1.0,
    'k1_y1': dict(alphaM=round(alphaM(1, 1), 3), share=round(share(1, 1), 3)),
    'k1_y0.1': dict(alphaM=round(alphaM(0.1, 1), 3), share=round(share(0.1, 1), 3)),
}
obs = {   # наблюдаемые произведения alpha·M
    'mammals_typical': 1 / 1.43,                 # [сн.] Charnov: E/alpha ≈ 1,43 у млекопитающих → alpha·M ≈ 0,70
    'orangutan': 0.28, 'gorilla': 0.21,          # [сн.] таблица из работы по инвариантам Чарнова
    'human_foragers_low': 15 * 0.010,            # [сн.] смертность взрослых собирателей 1–1,5 % в год; возраст зрелости 15–19 [пам.]
    'human_foragers_high': 19 * 0.015,
}
out['M1_fit_k1'] = {n: dict(alphaM=round(v, 3), y=round(y_from_alphaM(v, 1), 3), share_learned=round(share(y_from_alphaM(v, 1), 1), 2))
                    for n, v in obs.items()}
def elasticity(y, k): return -(k / (y + k)) / math.log(1 + k / y)
out['M1_elasticity_of_childhood_to_hazard'] = {f'y={y}': round(elasticity(y, 1), 2) for y in (0.05, 0.1, 0.3, 1, 3, 10)}
out['M1_childhood_ratio_when_hazard_doubles'] = {f'y={y}': round(math.log(1 + 1 / (2 * y)) / math.log(1 + 1 / y), 2) for y in (0.1, 1, 10)}

# ───────────────────────── М2. Число × вложение ─────────────────────────
# Родитель делит запас R на n потомков: n·(I0 + I) = R, I0 — неизбежная цена одного, I — вложение в умение.
# Максимум n·Q(I), Q(I) = 1 − exp(−I/theta):  exp(u) = 1 + iota + u,  u = I/theta, iota = I0/theta.
def u_star(iota):
    lo, hi = 1e-12, 50.0
    for _ in range(300):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if math.exp(mid) - mid < 1 + iota else (lo, mid)
    return (lo + hi) / 2
def n_numeric(theta, I0, R=1000.0):    # второй способ: перебор по сетке
    best = max(((R / (I0 + I)) * (1 - math.exp(-I / theta)), I) for I in np.linspace(1e-6, 60 * theta, 600001))
    return best[1]
chk = []
for theta, I0 in ((1, 1), (5, 1), (20, 1), (5, 10)):
    I_closed = u_star(I0 / theta) * theta
    chk.append(abs(I_closed - n_numeric(theta, I0)) / I_closed)
out['M2_check_max_rel_error'] = float(f'{max(chk):.1e}')
out['M2_number_vs_learning_scale'] = []
for theta in (1, 2, 4, 8, 16, 32):     # I0 = 1 закреплено: во сколько раз падает число потомков, когда учиться приходится дольше
    u = u_star(1 / theta); I = u * theta
    out['M2_number_vs_learning_scale'].append(dict(theta=theta, investment=round(I, 2), number_rel=round(100 / (1 + I), 1),
                                                  quality=round(1 - math.exp(-u), 3)))

# ───────────────────────── М3. Экзамен ─────────────────────────
# Доля усилий x идёт на показатель без пользы для дела. Правда T = a·(1 − x). Показатель P = a·(1 − x) + b·phi(x),
# phi(x) = (1 − exp(−lam·x))/lam (дыры кончаются). Раунд с вероятностью q оценивает экзамен (сила отбора bT, по T),
# иначе — показатель (сила bP, по P). Средний градиент логарифма приспособленности по x равен нулю при
#   phi'(x*) = (a/b)·(1 + S·q/(1 − q)),  S = bT/bP;   обман исчезает при  q/(1 − q) >= G/S,  G = (b − a)/a.
def q_star(G, S): return G / (G + S)
def x_star(q, a, b, lam, S):
    if q >= 1: return 0.0
    v = (b / a) / (1 + S * q / (1 - q))
    return min(1.0, max(0.0, math.log(v) / lam)) if v > 1 else 0.0
def phi(x, lam): return (1 - math.exp(-lam * x)) / lam

def simulate(q, a, b, lam, bP, bT, N=4000, gens=4000, sd=0.02, seed=0):
    """Та же модель со случайностью: N особей, отбор пропорционален exp(сила × оценка), мутации доли x."""
    r = np.random.default_rng(seed)
    x = np.full(N, 0.3)
    acc = []
    for g in range(gens):
        T = a * (1 - x)
        if r.random() < q: w = np.exp(bT * (T - T.max()))
        else:
            P = T + b * (1 - np.exp(-lam * x)) / lam
            w = np.exp(bP * (P - P.max()))
        x = x[r.choice(N, N, p=w / w.sum())] + r.normal(0, sd, N)
        x = np.abs(x); x = np.where(x > 1, 2 - x, x)          # отражение от границ 0 и 1
        if g >= gens // 2: acc.append(x.mean())
    return float(np.mean(acc))

a, b, lam, bP = 1.0, 2.0, 2.0, 3.0
out['M3_check'] = []
for S in (1.0, 4.0):
    qs = q_star((b - a) / a, S)
    row = dict(S=S, q_star_formula=round(qs, 3), points=[])
    for q in (0.0, 0.5 * qs, 0.8 * qs, qs, min(0.99, 1.3 * qs), min(0.99, 2 * qs)):
        row['points'].append(dict(q=round(q, 3), x_formula=round(x_star(q, a, b, lam, S), 3),
                                  x_simulated=round(simulate(q, a, b, lam, bP, S * bP, seed=int(1000 * q) + int(10 * S)), 3)))
    out['M3_check'].append(row)
out['M3_threshold_table'] = {f'G={G}': {f'S={S}': round(q_star(G, S), 3) for S in (0.1, 1, 10, 100)} for G in (0.1, 0.5, 1, 4, 10)}

# Цена. Раунд показателя стоит 1, раунд экзамена — C. Рост настоящего умения за единицу бюджета:
#   Pi(q) = (1 − x*(q)) · ((1 − q)·bP + q·bT) / ((1 − q) + q·C)
# Три кандидата в оптимум: q = 0 (терпеть обман), q = q* (экзамен на пороге), q = 1 (только правда).
#   C < S: лучше q = 1.   C > S: экзамен на пороге окупается, только если x0 > G·(C − S)/(S + G·C),
#   где x0 = x*(0) — доля усилий, уходящая в обман без экзамена.
def progress(q, a, b, lam, S, C, bP=1.0):
    return (1 - x_star(q, a, b, lam, S)) * ((1 - q) * bP + q * S * bP) / ((1 - q) + q * C)
def pays_threshold(G, S, C): return G * (C - S) / (S + G * C)
grid = np.linspace(0, 1, 2001)
out['M3_optimum'] = {}
for name, (lam_, S, C) in {'дыры быстро кончаются (lam=2), экзамен дорогой (S=4, C=40)': (2.0, 4, 40),
                            'дыры быстро кончаются (lam=2), экзамен умеренный (S=4, C=8)': (2.0, 4, 8),
                            'дыр много (lam=0,7), экзамен дорогой (S=4, C=40)': (0.7, 4, 40),
                            'дыр много (lam=0,7), экзамен умеренный (S=4, C=8)': (0.7, 4, 8),
                            'экзамен дешёвый (lam=2, S=4, C=2)': (2.0, 4, 2)}.items():
    vals = [progress(q, a, b, lam_, S, C) for q in grid]
    G = (b - a) / a
    out['M3_optimum'][name] = dict(x0=round(x_star(0, a, b, lam_, S), 3), q_star=round(q_star(G, S), 3),
                                   pays_if_x0_above=(round(pays_threshold(G, S, C), 3) if C > S else 'экзамен дешевле своей силы: q = 1'),
                                   q_best=round(float(grid[int(np.argmax(vals))]), 3),
                                   progress_q0=round(vals[0], 3), progress_qstar=round(progress(q_star(G, S), a, b, lam_, S, C), 3), progress_q1=round(vals[-1], 3))
# проверка правила на случайных параметрах: совпадает ли лучший q на сетке с выбором из трёх кандидатов
r2 = np.random.default_rng(7); agree = interior = 0; n_rand = 400
for _ in range(n_rand):
    bb, lam_, S, C = 1 + 10 ** r2.uniform(-1, 1), 10 ** r2.uniform(-0.5, 1), 10 ** r2.uniform(-1, 2), 10 ** r2.uniform(-1, 2.5)
    G = bb - 1; qs = q_star(G, S)
    vals = np.array([progress(q, 1.0, bb, lam_, S, C) for q in grid]); qb = float(grid[int(np.argmax(vals))])
    cand = {0.0: progress(0, 1.0, bb, lam_, S, C), qs: progress(qs, 1.0, bb, lam_, S, C), 1.0: progress(1, 1.0, bb, lam_, S, C)}
    best_c = max(cand.values())
    if vals.max() <= best_c * (1 + 1e-3): agree += 1
    elif min(abs(qb - c) for c in cand) > 2e-3: interior += 1
out['M3_optimum_rule_check'] = dict(random_cases=n_rand, best_is_one_of_three=agree, interior_optimum=interior)

# Числа из мира для сверки с М3 (не доказательство, а проверка «не противоречит»)
out['world_drift'] = dict(
    ussr_indicator_drift_per_year=round(math.log(90 / 6.9) / (1989 - 1928), 4),   # [сн., отчёт Neu 09.10]: официально ×90, по Ханину ×6,9 за 1928–1989
    autocracy_gdp_growth_overstatement=0.35,                                       # [сн.] Martinez 2022
    us_gpa_drift_per_year=round((3.36 - 3.17) / (2021 - 2010), 4),                 # [сн.] ACT: средний балл 3,17 → 3,36 при падении ACT 21,0 → 20,3
    swe_bench_tests_minus_merge_pp=24,                                             # [сн.] METR, март 2026
)

# ───────────────────────── Добавлено после критики, цикл 1 ─────────────────────────
# М1: что даёт формула при разных определениях цены ожидания h для людей (замечания Б3, Б4): число не одно.
out['M1_humans_by_definition'] = {
    'h = смертность лучших лет 1–1,5 % [сн.]; зрелость 15–19 [пам.]': [round(15 * 0.010, 2), round(19 * 0.015, 2)],
    'h = 1/E, E = 30–40 лет взрослой жизни [сн.: больше чем вдвое против шимпанзе ≈ 15]; зрелость 17–19': [round(17 / 40, 2), round(19 / 30, 2)],
    'h = 1/срок размножения 25–27 лет [пам.] + 1 %; зрелость 18': [round(18 * (1 / 27 + 0.01), 2), round(18 * (1 / 25 + 0.01), 2)],
}
# М2 с помощью группы (замечание Б5): запас R·(1 + H), H — помощь относительно вклада матери. Вложение I* то же, число растёт в (1 + H) раз.
out['M2_with_helpers'] = []
for theta, H in ((4, 0.0), (16, 0.0), (16, 1.0), (16, 2.0)):
    u = u_star(1 / theta); I = u * theta
    out['M2_with_helpers'].append(dict(theta=theta, help_H=H, investment=round(I, 2), number_rel=round(100 * (1 + H) / (1 + I), 1)))
# М4 (замечание Б10): w_ij = 1 + B·zbar_j − c·z_ij. По Прайсу признак растёт при F > c/B, F — доля межгрупповой дисперсии.
r4 = np.random.default_rng(11); agree_F = agree_odds = n_m4 = 0
for _ in range(2000):
    ng, m = int(r4.integers(5, 40)), int(r4.integers(3, 30))
    B, c = float(r4.uniform(0.01, 1.0)), float(r4.uniform(0.005, 0.5))
    z = np.clip(r4.normal(r4.uniform(0.2, 0.8, ng)[:, None] * float(r4.uniform(0, 1)) + 0.5 * (1 - float(r4.uniform(0, 1))), float(r4.uniform(0.05, 0.3)), (ng, m)), 0, 1)
    w = 1 + B * z.mean(axis=1, keepdims=True) - c * z
    dz = (w * z).mean() / w.mean() - z.mean()                      # изменение среднего признака за поколение
    F = z.mean(axis=1).var() / z.var()
    if abs(F - c / B) < 1e-3 or abs(F / (1 - F) - c / B) < 1e-3: continue
    n_m4 += 1; agree_F += (dz > 0) == (F > c / B); agree_odds += (dz > 0) == (F / (1 - F) > c / B)
out['M4_check'] = dict(cases=n_m4, sign_matches_F_gt_c_over_B=int(agree_F), sign_matches_odds_form=int(agree_odds))
# СССР: расхождение зависит от того, какую оценку взять за правду (замечание Э2)
out['world_drift']['ussr_by_truth_estimate'] = dict(
    khanin_x6_9=round(math.log(90 / 6.9) / 61, 4),                 # [сн., отчёт 09.10; период 1928–1989 одним источником]
    ofer_4_2pct_growth=round(math.log(90 / 1.042 ** 61) / 61, 4),   # [сн., отчёт 09.10]: ВНП рос на 4,2 % в год → ×12,3 за 61 год
    ofer_factor=round(1.042 ** 61, 1))
out['world_drift']['olken_share_left_at_full_audit'] = round(19.2 / 27.7, 2)   # [сн., J-PAL]: «пропажа» 27,7 → 19,2 % при аудите 4 → 100 %

# ───────────────────────── Добавлено после критики, цикл 2 (замечания математика) ─────────────────────────
# М3 при ранговом отборе (замечание 1): та же модель, но отбор — турнир. Формула порога G/S выведена для отбора по величине оценки.
def simulate_rank(q, a, b, lam, tour=5, tour_exam=None, N=3000, gens=3000, sd=0.02, seed=0):
    r = np.random.default_rng(seed); x = np.full(N, 0.3); acc = []
    for g in range(gens):
        T = a * (1 - x); exam = r.random() < q
        sc = T if exam else T + b * (1 - np.exp(-lam * x)) / lam
        k = (tour_exam or tour) if exam else tour
        c = r.integers(N, size=(N, k)); idx = c[np.arange(N), np.argmax(sc[c], axis=1)]
        x = np.abs(x[idx] + r.normal(0, sd, N)); x = np.where(x > 1, 2 - x, x)
        if g >= gens // 2: acc.append(x.mean())
    return float(np.mean(acc))
out['M3_rank_selection'] = dict(note='доля обмана x: формула (отбор по величине, S = 1) против турнира; a = 1, lam = 2', rows=[])
for q in (0.0, 0.2, 0.35, 0.45, 0.55, 0.7):
    out['M3_rank_selection']['rows'].append(dict(q=q, formula_G1=round(x_star(q, 1.0, 2.0, 2.0, 1.0), 3),
        tournament5_G1=round(simulate_rank(q, 1.0, 2.0, 2.0, seed=2), 3), tournament5_G3=round(simulate_rank(q, 1.0, 4.0, 2.0, seed=4), 3),
        exam_tournament20_proxy_tournament2_G1=round(simulate_rank(q, 1.0, 2.0, 2.0, tour=2, tour_exam=20, seed=3), 3)))
out['M3_rank_selection']['formula_threshold'] = dict(G1_S1=0.5, G3_S1=0.75)
# М3: все точки стохастической проверки (замечание 7) — не только лучшие
out['M3_check_all_points_abs_error'] = [dict(S=row['S'], q=p_['q'], formula=p_['x_formula'], simulated=p_['x_simulated'],
                                             error=round(p_['x_simulated'] - p_['x_formula'], 3)) for row in out['M3_check'] for p_ in row['points']]
# М3′ — смесь в одном показателе P' = (1 − q)·P + q·T (замечание 10): точный максимум против формулы 1 − q·(1 + G)/G
def dilution_exact(G, q, lam=2.0, a_=1.0):
    b_ = a_ * (1 + G); xs = np.linspace(0, 1, 200001)
    x = xs[int(np.argmax(a_ * (1 - xs) + (1 - q) * b_ * (1 - np.exp(-lam * xs)) / lam))]
    return (1 - q) * b_ * (1 - math.exp(-lam * x)) / lam
out['M3_mixture'] = {f'G={G}': dict(exact=[round(dilution_exact(G, q) / dilution_exact(G, 0), 3) for q in (0.125, 0.25, 0.5)],
                                    formula=[round(max(0.0, 1 - q * (1 + G) / G), 3) for q in (0.125, 0.25, 0.5)]) for G in (1, 3, 10)}
out['M3_mixture']['upper_bound_1_minus_q'] = [0.875, 0.75, 0.5]
# Самообман оценщика под отбором (замечание 5): P = T + шум, отбор верхней доли. В единицах разброса правды: (1 − rho²)·i/rho.
def intensity(p_):
    lo, hi = -10.0, 10.0
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if 0.5 * math.erfc(mid / math.sqrt(2)) > p_ else (lo, mid)
    z = (lo + hi) / 2; return math.exp(-z * z / 2) / math.sqrt(2 * math.pi) / p_
r5 = np.random.default_rng(0); T5 = r5.normal(size=2_000_000); e5 = r5.normal(size=2_000_000)
out['selection_on_proxy_raw'] = []
for rho in (0.9, 0.5):
    P5 = T5 + e5 * math.sqrt((1 - rho ** 2) / rho ** 2); top = P5 >= np.quantile(P5, 0.99); i1 = intensity(0.01)
    out['selection_on_proxy_raw'].append(dict(rho=rho, top_share=0.01, raw_formula=round((1 - rho ** 2) * i1 / rho, 3), raw_simulated=round(float(np.mean(P5[top] - T5[top])), 3),
                                               standardized_formula=round((1 - rho) * i1, 3), calibrated_claim_simulated=round(float(np.mean(rho ** 2 * P5[top] - T5[top])), 3)))
# М1 из уравнения Эйлера — Лотки (замечание 6): 1 = Q(tau)·exp(−(mu_j + r)·tau)/(mu_a + r); максимум r по tau → Q'/Q = mu_j + r
def r_of(tau, theta, k, mj, ma):
    Q = (1 - math.exp(-tau / theta)) ** k; lo, hi = -ma + 1e-9, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if Q * math.exp(-(mj + mid) * tau) / (ma + mid) > 1 else (lo, mid)
    return (lo + hi) / 2
out['M1_euler_lotka'] = []
for ma in (0.05, 0.1, 0.2, 0.4):
    taus = np.linspace(0.5, 30, 5901); rs = [r_of(t, 5, 3, 0.05, ma) for t in taus]; j = int(np.argmax(rs))
    out['M1_euler_lotka'].append(dict(adult_mortality=ma, tau_max_r=round(float(taus[j]), 2), r=round(rs[j], 3),
                                      formula_h_juvenile_plus_r=round(tau_star(5, 3, 0.05 + rs[j]), 2), formula_h_juvenile_plus_adult=round(tau_star(5, 3, 0.05 + ma), 2)))
# М2 (замечание 9): помощь, которая покрывает неизбежную цену потомка I0, снижает и оптимальное вложение
out['M2_help_into_fixed_cost'] = [dict(theta=16, I0=I0, investment=round(u_star(I0 / 16) * 16, 2), number_rel=round(100 / (I0 + u_star(I0 / 16) * 16), 1)) for I0 in (1.0, 0.5, 0.25)]

# ───────────────────────── Добавлено после критики, цикл 3 (арбитр и моя проверка) ─────────────────────────
# М3б — частный случай: стоит появиться разбросу правды, не связанному с обманом (умение дня, шум), и турнир снова «видит величину».
def simulate_rank_spread(q, b, noise, lam=2.0, a=1.0, tour=5, N=3000, gens=3000, sd=0.02, seed=0):
    r = np.random.default_rng(seed); x = np.full(N, 0.3); acc = []
    for g in range(gens):
        T = a * (1 - x) + r.normal(0, noise, N)                       # ненаследуемый разброс правды, общий для T и P
        exam = r.random() < q
        sc = T if exam else T + b * (1 - np.exp(-lam * x)) / lam
        c = r.integers(N, size=(N, tour)); idx = c[np.arange(N), np.argmax(sc[c], axis=1)]
        x = np.abs(x[idx] + r.normal(0, sd, N)); x = np.where(x > 1, 2 - x, x)
        if g >= gens // 2: acc.append(x.mean())
    return round(float(np.mean(acc)), 3)
out['M3_rank_with_truth_spread'] = dict(note='доля обмана x при турнире 5; разброс правды 0 — частный случай М3б; при разбросе 0,05 и 0,5 перелом возвращается к G/(1 + G)', rows={})
for b_, G_ in ((2.0, 1), (4.0, 3)):
    for noise in (0.0, 0.05, 0.5):
        out['M3_rank_with_truth_spread']['rows'][f'G={G_}, разброс правды {noise}'] = {
            str(q): simulate_rank_spread(q, b_, noise, seed=int(100 * q + 10 * b_ + 1000 * noise)) for q in (0.0, 0.3, 0.45, 0.55, 0.65, 0.75, 0.85)}
out['M3_rank_with_truth_spread']['formula_M3a_S1'] = {f'G={G_}': {str(q): round(x_star(q, 1.0, 1.0 + G_, 2.0, 1.0), 3) for q in (0.0, 0.3, 0.45, 0.55, 0.65, 0.75, 0.85)} for G_ in (1, 3)}
# М1: таблица математика воспроизводится при плодовитости m = 2 (арбитр, А3)
def r_of_m(tau, theta, k, mj, ma, m_):
    Q = m_ * (1 - math.exp(-tau / theta)) ** k; lo, hi = -ma + 1e-9, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if Q * math.exp(-(mj + mid) * tau) / (ma + mid) > 1 else (lo, mid)
    return (lo + hi) / 2
out['M1_euler_lotka_m2'] = []
for ma in (0.05, 0.1, 0.2, 0.4):
    taus = np.linspace(0.5, 30, 5901); rs = [r_of_m(t, 5, 3, 0.05, ma, 2.0) for t in taus]; j = int(np.argmax(rs))
    out['M1_euler_lotka_m2'].append(dict(adult_mortality=ma, tau_max_r=round(float(taus[j]), 2), r=round(rs[j], 3)))
# геном против схемы связей: человек и мышь (арбитр, А2): разрыв есть у обоих, но разной величины
out['genome_vs_wiring_human_and_mouse'] = dict(human=round(1e14 * math.log2(8.6e10) / 6.2e9), mouse=round(1e11 * math.log2(7e7) / 5.4e9),
                                               note='числа синапсов и нейронов — по памяти')

# готовые таблицы «что формулы дают в числах» (цикл 3): порог экзамена и завышение сырой оценки под отбором
out['M3_threshold_grid'] = dict(note='доля экзамена q* = G/(G + S), при которой обман исчезает (М3а, экспоненциальные дыры); x при q чуть ниже и чуть выше порога — проверка',
                                 rows={f'G={G_}': {f'S={S_}': round(q_star(G_, S_), 3) for S_ in (1, 3, 10)} for G_ in (0.25, 1, 3, 10)})
out['M3_threshold_grid']['check_x_just_below_and_above'] = {
    f'G={G_}, S={S_}': [round(x_star(q_star(G_, S_) - 0.02, 1.0, 1.0 + G_, 2.0, S_), 4), round(x_star(min(0.999, q_star(G_, S_) + 0.02), 1.0, 1.0 + G_, 2.0, S_), 4)]
    for G_ in (0.25, 1, 3, 10) for S_ in (1, 3, 10)}
r6 = np.random.default_rng(1); T6 = r6.normal(size=2_000_000); e6 = r6.normal(size=2_000_000)
out['evaluator_inflation_table'] = dict(note='завышение сырой оценки у отобранных, (1 − ρ²)·i/ρ, в единицах разброса правды; в скобках проверка на 2 млн пар', rows={})
for rho in (0.95, 0.9, 0.7, 0.5):
    P6 = T6 + e6 * math.sqrt((1 - rho ** 2) / rho ** 2); row = {}
    for top_ in (0.5, 0.1, 0.01, 0.001):
        sel = P6 >= np.quantile(P6, 1 - top_)
        row[f'верхние {top_}'] = dict(formula=round((1 - rho ** 2) * intensity(top_) / rho, 2), simulated=round(float((P6[sel] - T6[sel]).mean()), 2))
    out['evaluator_inflation_table']['rows'][f'rho={rho}'] = row

# ───────────────────────── Пороги и мощность знаковых проверок (к PREREG-DEFER-01) ─────────────────────────
def binom_tail(n, k, p):               # P(X >= k)
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))
def threshold(n, alpha=0.01):
    return next(k for k in range(n + 1) if binom_tail(n, k, 0.5) <= alpha)
out['sign_test'] = {}
for n in (40, 50, 60, 100, 120):
    k = threshold(n)
    out['sign_test'][n] = dict(k=k, false_level=round(binom_tail(n, k, 0.5), 4),
                               power={p: round(binom_tail(n, k, p), 2) for p in (0.6, 0.65, 0.7, 0.75, 0.8)})

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '2026-11-27_deferred_selection_models.json')
json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
