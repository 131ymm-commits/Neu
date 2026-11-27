"""Расчёты к эссе docs/2026-11-27_deferred_selection.md («Отсрочка отбора»). Иллюстрации, не опыт.
Входные числа помечены: [сн.] — сниппет поиска 27.11.2026, [пам.] — по памяти, не проверено.
Запуск: python3 docs/2026-11-27_deferred_selection_calc.py — пишет docs/2026-11-27_deferred_selection_calc.json."""
import json, math, os

out = {}

# 1. Годовой риск гибели за «детство» (до 15 лет): mu = -ln(1 - p15) / 15
p15_past = 0.488           # [сн.] Volk & Atkinson 2013 по странице HRAF: средняя детская смертность 48,8 % (SD 5,8 %)
u5_world_2024 = 0.0374     # [сн.] UN IGME (выпуск 2026 г.): 37,4 на 1000 живорождений в 2024 году
q5_14_world = 0.007        # [пам.] вероятность умереть в 5–14 лет, мир — около 7 на 1000
p15_world = u5_world_2024 + (1 - u5_world_2024) * q5_14_world
p15_rich = 0.006           # [пам.] богатые страны: около 0,6 % до 15 лет
mu = {k: -math.log(1 - p) / 15 for k, p in (('past', p15_past), ('world_2024', p15_world), ('rich', p15_rich))}
out['juvenile_hazard_per_year'] = {k: round(v, 5) for k, v in mu.items()}
out['p_die_before_15'] = dict(past=p15_past, world_2024=round(p15_world, 4), rich=p15_rich)
out['hazard_ratio_past_to_world'] = round(mu['past'] / mu['world_2024'], 1)
out['hazard_ratio_past_to_rich'] = round(mu['past'] / mu['rich'], 0)

# 2. Пропускная способность: отбор против обучения
kimura_bits_per_gen = 0.29                 # [сн.] Kimura 1960/1961: H = Le/ln2 ≈ 0,29 бита на поколение
genome_bp = 3.1e9                          # [пам.] длина генома человека, пар оснований
G = 2 * genome_bp                          # бит: не больше 2 бит на пару
mackay_bits_per_gen = math.sqrt(G)         # [сн.] MacKay (гл. 19): порядка sqrt(G) бит на поколение при рекомбинации; модель оспорена (Worden 2022)
lang_bits_per_day = 1900                   # [сн.] Mollica & Piantadosi 2019: лучшая оценка, диапазон 121–6204
lang_days = 18 * 365                       # [сн.] допущение авторов: 18 лет по 365 дней
lang_bits = lang_bits_per_day * lang_days
sunfish_eggs, survivors = 3e8, 2           # [пам.] луна-рыба: до 300 млн икринок; при постоянной численности выживают двое
out['selection_vs_learning'] = dict(
    truncation_half_bits=math.log2(1 / 0.5),
    sunfish_max_bits_per_generation=round(math.log2(sunfish_eggs / survivors), 1),
    kimura_bits_per_generation=kimura_bits_per_gen,
    genome_capacity_bits=G, genome_capacity_megabytes=round(G / 8 / 1e6),
    mackay_bound_bits_per_generation=round(mackay_bits_per_gen),
    language_bits_by_18=lang_bits, language_megabytes=round(lang_bits / 8 / 1e6, 2),
    language_over_kimura=round(lang_bits / kimura_bits_per_gen),
    language_over_mackay=round(lang_bits / mackay_bits_per_gen),
)

# 3. Геном против схемы связей мозга
neurons = 8.6e10                           # [сн.] 86 млрд нейронов (Herculano-Houzel; в отчёте Neu 09.10.2026)
synapses = 1e14                            # [пам.] порядка 10^14 синапсов (оценки 10^14–10^15)
wiring_bits = synapses * math.log2(neurons)
out['genome_vs_wiring'] = dict(bits_per_synapse_address=round(math.log2(neurons), 1), wiring_bits=float(f'{wiring_bits:.3g}'),
                               ratio_wiring_to_genome=float(f'{wiring_bits / G:.2g}'))

# 4. Смит — Фретвелл: W = (R / I) * f(I); оптимум f'(I) = f(I) / I. Условная кривая f(I) = 1 - exp(-(I - I0) / k), I > I0.
def sf_opt(I0, k):
    g = lambda I: math.exp(-(I - I0) / k) / k - (1 - math.exp(-(I - I0) / k)) / I   # f' - f/I
    lo, hi = I0 + 1e-9, I0 + 200 * k
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if g(mid) > 0 else (lo, mid)
    return (lo + hi) / 2
R = 100.0
out['smith_fretwell_toy'] = []
for k in (0.5, 2, 8, 32):                  # k — «длина кривой отдачи»: чем больше, тем дольше окупается вложение
    I = sf_opt(1.0, k)
    out['smith_fretwell_toy'].append(dict(k=k, optimal_investment=round(I, 2), offspring_number=round(R / I, 1),
                                          survival_each=round(1 - math.exp(-(I - 1.0) / k), 3)))

# 5. Оценщик под отбором: при двумерной нормальности E[T | P] = rho * P, самообман (заявлено − правда) = (1 − rho) * i,
#    i — интенсивность отбора (среднее P у отобранной верхней доли, в стандартных отклонениях).
def phi(z): return math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
def tail(z): return 0.5 * math.erfc(z / math.sqrt(2))
def intensity(p):
    lo, hi = -10.0, 10.0
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if tail(mid) > p else (lo, mid)
    z = (lo + hi) / 2
    return phi(z) / p
out['selection_on_proxy'] = []
for p in (0.5, 0.1, 0.01, 1e-4, 1e-6):
    i = intensity(p)
    out['selection_on_proxy'].append(dict(top_share=p, intensity=round(i, 3),
                                          **{f'self_deception_rho_{r}': round((1 - r) * i, 3) for r in (0.9, 0.7, 0.5)}))

# 6. «Сколько учиться»: W(tau) = exp(-(mu + r) * tau) * Q(tau) -> Q'/Q = mu + r. Для Q = tau^k: tau* = k / (mu + r).
#    Здесь только отношение: во сколько раз вырос бы оптимум при падении mu (r = 0) — верхняя граница, не прогноз.
out['learning_time_ratio_if_only_mu'] = dict(world=out['hazard_ratio_past_to_world'], rich=out['hazard_ratio_past_to_rich'])

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '2026-11-27_deferred_selection_calc.json')
json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
