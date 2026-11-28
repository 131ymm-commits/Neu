"""Проверки расчётом к разбору аналогий (docs/2026-11-28_math_analogies.md). Игрушки: правды от кода опытов здесь нет.
python3 2026-11-28_math_analogies_checks.py → 2026-11-28_math_analogies_checks.json"""
import json, math, os
import numpy as np
out = {}

# 1. Порог «редкий жёсткий экзамен против частого мягкого показателя»: линейная запись и запись в логарифмах.
#    Обманщик в раунде показателя размножается в (1 + g) раз лучше честного, в раунде экзамена — в (1 − s) раз.
#    Долгий рост обманщика: (1 − q)·ln(1 + g) + q·ln(1 − s). Порог: q* = ln(1 + g) / (ln(1 + g) − ln(1 − s)).
def q_log(g, s): return math.log(1 + g) / (math.log(1 + g) - math.log(1 - s))
def q_lin(g, s): return g / (g + s)
def wf(q, g, s, N=20000, gens=3000, reps=20, seed=0):
    """Райт — Фишер, два типа; доля обманщиков в конце (среднее по повторам); старт с 0,5."""
    r = np.random.default_rng(seed); fin = []
    for _ in range(reps):
        p = 0.5
        for t in range(gens):
            w = (1 - s) if r.random() < q else (1 + g)
            p = p * w / (p * w + (1 - p)); p = r.binomial(N, p) / N
            if p == 0 or p == 1: break
        fin.append(p)
    return round(float(np.mean(fin)), 3)
rows = []
for g, s in ((1.0, 0.5), (1.0, 0.9), (1.0, 0.99), (0.25, 0.5), (3.0, 0.5), (0.1, 0.1)):
    ql, qn = q_log(g, s), q_lin(g, s)
    rows.append(dict(g=g, s=s, q_log=round(ql, 3), q_lin=round(qn, 3),
                     cheaters_below_log=wf(max(0.0, ql - 0.07), g, s, seed=1), cheaters_above_log=wf(min(1.0, ql + 0.07), g, s, seed=2),
                     cheaters_at_lin=wf(qn, g, s, seed=3)))
out['threshold_log_vs_linear'] = dict(note='доля обманщиков в конце: на 0,07 ниже и выше логарифмического порога и на линейном пороге', rows=rows)

# 2. Дрейф оценщика с редкой сверкой: ошибка растёт в a раз за раунд, с вероятностью q сверка возвращает её к 1.
#    Второй момент ограничен при (1 − q)·a² < 1, то есть q > 1 − 1/a² (тот же вид, что у Калмана с пропадающими измерениями).
#    Хвост распределения ошибки степенной: P(ошибка > x) ~ x^(−alpha), alpha = ln(1/(1 − q)) / ln a.
def drift(q, a, T=400000, seed=0, periodic=False):
    r = np.random.default_rng(seed); e = 1.0; xs = np.empty(T); k = max(1, round(1 / q)) if q > 0 else 10 ** 9
    for t in range(T):
        reset = (t % k == k - 1) if periodic else (r.random() < q)
        e = 1.0 if reset else e * a
        xs[t] = e
    return xs
rows = []
for a, q in ((1.2, 0.2), (1.2, 0.4), (1.5, 0.3), (1.5, 0.6)):
    x = drift(q, a, seed=int(100 * a + 10 * q)); xp = drift(q, a, periodic=True)
    alpha = math.log(1 / (1 - q)) / math.log(a)
    xs = np.sort(x)[::-1]; k = 2000; hill = 1 / np.mean(np.log(xs[:k] / xs[k]))          # оценка Хилла показателя хвоста
    rows.append(dict(a=a, q=q, q_critical=round(1 - 1 / a ** 2, 3), alpha_formula=round(alpha, 2), alpha_hill=round(float(hill), 2),
                     median=round(float(np.median(x)), 2), q999=round(float(np.quantile(x, 0.999)), 1),
                     periodic_max=round(float(xp.max()), 2), periodic_median=round(float(np.median(xp)), 2)))
out['drift_with_resets'] = dict(note='случайная сверка даёт степенной хвост ошибки; сверка по расписанию с той же частотой хвоста не даёт', rows=rows)

# 3. Сколько бит о тестах утекло в выбор: граница Руссо — Цзоу, завышение ≤ sigma·sqrt(2·I), I — в натах.
#    Выбор лучшего из N равных по правде кандидатов с независимым гауссовым шумом: завышение = E max.
r = np.random.default_rng(0); rows = []
for N in (2, 5, 30, 300, 3000):
    emax = float(np.mean(r.normal(size=(20000, N)).max(1)))
    rows.append(dict(N=N, inflation=round(emax, 3), bound=round(math.sqrt(2 * math.log(N)), 3), bits=round(math.log2(N), 2)))
out['russo_zou_best_of_N'] = dict(note='завышение лучшего из N в единицах шума против границы sqrt(2 ln N)', rows=rows)
# обратное чтение: наименьшее число бит, утёкших в выбор, при наблюдённом завышении W и шуме sigma = 0,125 (16 тестов, правда около 0,5)
out['bits_from_inflation'] = {str(W): round((W / 0.125) ** 2 / 2 / math.log(2), 2) for W in (0.02, 0.066, 0.154, 0.44, 0.75)}

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '2026-11-28_math_analogies_checks.json')
json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
