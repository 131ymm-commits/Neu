#!/usr/bin/env python3
# TESTER-01: мощность парного сравнения рук по внесённым багам (до пилота; модель — допущение).
# Модель: у бага трудность d ~ N(0, 1); вероятность, что рука найдёт баг, — logistic(θ_руки − d); руки независимы при данном баге.
# Тест: точный односторонний знаковый тест по несовпавшим багам (найден одной рукой и не найден другой), α по Холму: 0,025 для первого из двух.
import json, math, random
def sign_p(k, n): return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n if n else 1.0
def theta(p):  # θ, при котором средняя доля найденных по трудностям N(0,1) ≈ p
    lo, hi = -8, 8
    for _ in range(60):
        mid = (lo + hi) / 2; m = sum(1 / (1 + math.exp(-(mid - d))) for d in GRID) / len(GRID)
        lo, hi = (mid, hi) if m < p else (lo, mid)
    return (lo + hi) / 2
random.seed(20261109); GRID = [random.gauss(0, 1) for _ in range(4000)]
def power(pA, pB, nbugs, reps=1, alpha=0.025, sims=4000, seed=1):
    rnd = random.Random(seed); tA, tB = theta(pA), theta(pB); hit = 0
    for _ in range(sims):
        win = lose = 0
        for _ in range(nbugs):
            d = rnd.gauss(0, 1); a = sum(rnd.random() < 1 / (1 + math.exp(-(tA - d))) for _ in range(reps)); b = sum(rnd.random() < 1 / (1 + math.exp(-(tB - d))) for _ in range(reps))
            win += a > b; lose += b > a
        hit += sign_p(win, win + lose) <= alpha
    return round(hit / sims, 3)
out = {}
for nb, reps in ((16, 1), (16, 2), (32, 1)):
    for pA, pB in ((0.6, 0.2), (0.5, 0.25), (0.6, 0.4), (0.4, 0.3)):
        out[f'{nb} багов × {reps} сесс.: {pA} против {pB}'] = power(pA, pB, nb, reps)
for k, v in out.items(): print(k, '→ мощность', v)
json.dump({'model': 'трудность N(0,1), logistic(θ−d), знаковый тест односторонний, α 0,025 (Холм, первый из двух)', 'power': out}, open('power_tester01.json', 'w'), ensure_ascii=False, indent=1)
