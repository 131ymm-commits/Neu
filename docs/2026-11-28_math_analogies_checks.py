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

# 4. (после критики) Конечная популяция с притоком обходчиков: редкий смертельный экзамен — случайный против экзамена по расписанию.
#    Райт — Фишер, N = 20000, приток обходчиков 1e-4 за поколение (в одну сторону), g = 1; 20000 поколений, 5 повторов.
def wf_inflow(q, g, s, N=20000, mu=1e-4, gens=20000, periodic=False, seed=0):
    r = np.random.default_rng(seed); pp = 0.0; acc = []
    for t in range(gens):
        # расписание — то же правило, что в опыте CHILD-01: ровно доля q поколений, равномерно (прежде стояло «каждое round(1/q)-е», что при q = 0,4 давало долю 0,5)
        exam = (int((t + 1) * q + 1e-9) > int(t * q + 1e-9)) if periodic else (r.random() < q)
        w = (1 - s) if exam else (1 + g); den = pp * w + (1 - pp)
        pp = pp * w / den if den > 0 else 0.0
        pp = pp + (1 - pp) * mu; pp = r.binomial(N, min(1.0, pp)) / N
        if t >= gens // 2: acc.append(pp)
        if pp >= 1.0: return 1.0, True
    return float(np.mean(acc)), False
rows = []
for s_ in (0.9999, 1.0):
    for q_ in (0.1, 0.2, 0.4):
        rnd = [wf_inflow(q_, 1.0, s_, seed=i) for i in range(5)]; per = [wf_inflow(q_, 1.0, s_, periodic=True, seed=10 + i) for i in range(5)]
        rows.append(dict(s=s_, q=q_, q_log=0.0 if s_ >= 1 else round(q_log(1.0, s_), 3), random_fixed_of_5=int(sum(x[1] for x in rnd)), random_mean_share=round(float(np.mean([x[0] for x in rnd])), 3),
                         periodic_fixed_of_5=int(sum(x[1] for x in per)), periodic_mean_share=round(float(np.mean([x[0] for x in per])), 4)))
out['finite_population_with_inflow'] = dict(note='случайный экзамен допускает длинные паузы; если пауза длиннее времени захвата, честных не остаётся', rows=rows,
    takeover_generations=round(math.log(20000 / 1e-4) / math.log(2), 1), p_gap_longer_than_takeover={str(q_): float(f'{(1 - q_) ** 27:.2g}') for q_ in (0.1, 0.2, 0.4)},
    half_generations=round(math.log(1 / 1e-4) / math.log(2), 1),                    # до половины популяции; до полного вытеснения честных — takeover_generations
    expected_long_gaps_per_run={str(q_): float(f'{20000 * q_ * (1 - q_) ** 27:.2g}') for q_ in (0.1, 0.2, 0.4)},   # сколько раз за 20000 поколений случайный экзамен даёт паузу длиннее 27 поколений
    longest_gap_periodic={str(q_): max(len(x) for x in ''.join('1' if int((t + 1) * q_ + 1e-9) > int(t * q_ + 1e-9) else '0' for t in range(2000)).split('1')) for q_ in (0.1, 0.2, 0.4)})
# 5. (после критики) Порог рассчитывающего нарушителя (линейная полезность) против порога отбора (логарифмы): форма одна, величины разные
out['deterrence_vs_selection'] = [dict(g=g_, s=s_, deterrence=round(q_lin(g_, s_), 3), selection=round(q_log(g_, s_), 3)) for g_, s_ in ((1.0, 0.5), (1.0, 0.9), (0.1, 0.1), (0.01, 0.01))]
# 6. (после критики) «Число независимых выборов»: какому «лучшему из N» отвечает наблюдённое завышение в единицах шума
def emax(N, reps=40000, rr=np.random.default_rng(5)): return float(np.mean(rr.normal(size=(reps, N)).max(1)))
tab = {N: round(emax(N), 3) for N in (2, 3, 4, 5, 6, 8, 10, 20)}
out['effective_number_of_choices'] = dict(emax=tab, inflation_in_sigma=round(0.154 / 0.125, 2), programs_examined_per_run=300 * 150,
                                          note='завышение 0,154 при шуме 0,125 — как у лучшего из 5–6 независимых равных кандидатов')
# 7. (после критики) Экзамены в Англии: какой сдвиг нормального распределения переводит 75,5 % в 88,2 % и во сколько раз он увеличивает хвост в 1 %
from statistics import NormalDist
nd = NormalDist(); sh = nd.inv_cdf(0.882) - nd.inv_cdf(0.755); z1 = nd.inv_cdf(0.99)
out['tail_mechanics'] = dict(shift_sigma=round(sh, 3), tail_1pct_multiplier=round((1 - nd.cdf(z1 - sh)) / 0.01, 2), observed_multiplier=round(12950 / 2785, 2))
# 7б. (после арбитра) тот же сдвиг при другой доле верхушки: долю учеников с тремя высшими оценками я не проверял
out['tail_mechanics']['multiplier_by_base_share'] = {str(b): round((1 - nd.cdf(nd.inv_cdf(1 - b) - sh)) / b, 2) for b in (0.01, 0.005, 0.002)}
# 4б. (после арбитра) Экзамен по расписанию с периодом k (пауза k − 1 поколение), экзамен убивает всех обходчиков: захват и средняя доля обходчиков.
#     Вопрос: когда наступает вред (большая доля обходчиков) и когда — необратимый захват. Детерминированные оценки: половина — 13,3 поколения, полное вытеснение — 27,6.
def wf_period(k, g=1.0, N=20000, mu=1e-4, gens=20000, seed=0):
    r = np.random.default_rng(seed); pp = 0.0; acc = []
    for t in range(gens):
        if t % k == k - 1: pp = 0.0                      # экзамен: обходчиков не остаётся
        else: pp = pp * (1 + g) / (pp * (1 + g) + (1 - pp))
        pp = pp + (1 - pp) * mu; pp = r.binomial(N, min(1.0, pp)) / N
        if pp >= 1.0: return 1.0, True
        acc.append(pp)
    return float(np.mean(acc[gens // 2:])), False
rows = []
for k in (10, 14, 17, 20, 22, 23, 24, 25, 26, 28):
    res = [wf_period(k, seed=100 + i) for i in range(10)]
    rows.append(dict(gap=k - 1, fixed_of_10=int(sum(x[1] for x in res)), mean_share_not_fixed=None if all(x[1] for x in res) else round(float(np.mean([x[0] for x in res if not x[1]])), 3)))
out['periodic_gap_scan'] = dict(note='экзамен по расписанию каждые k поколений: число захватов из 10 и средняя доля обходчиков там, где захвата нет', rows=rows,
    shortest_gap_with_fixation=min(r_['gap'] for r_ in rows if r_['fixed_of_10'] > 0), longest_gap_without_fixation=max(r_['gap'] for r_ in rows if r_['fixed_of_10'] == 0),
    # сколько раз за 20000 поколений случайный экзамен с долей q даёт паузу не короче 23 поколений
    expected_gaps_23_or_longer_per_run={str(q_): float(f'{20000 * q_ * (1 - q_) ** 23:.2g}') for q_ in (0.1, 0.2, 0.4)})
# 8. (после критики) Порог для первого и для второго момента при умножительном дрейфе со сбросом
out['drift_thresholds'] = [dict(a=a_, mean_bounded_if_q_above=round(1 - 1 / a_, 3), second_moment_bounded_if_q_above=round(1 - 1 / a_ ** 2, 3)) for a_ in (1.2, 1.5)]

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '2026-11-28_math_analogies_checks.json')
json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
