"""CHILD-01: таблицы отчёта из facts.json — чтобы числа отчёта не набирались руками. Написан и закоммичен до конца основного прогона.
  python3 report_tables.py [pilot|test] → report_tables.md (для pilot — report_tables_pilot.md)"""
import json, os, sys
H = os.path.dirname(os.path.abspath(__file__)); mode = sys.argv[1] if len(sys.argv) > 1 else 'test'
F = json.load(open(os.path.join(H, 'facts_pilot.json' if mode == 'pilot' else 'facts.json')))
FP = json.load(open(os.path.join(H, 'facts_pilot.json')))                      # пилот (сиды 990–992) — для столбца «в пилоте»
def n(x, d=3):
    if x is None: return '—'
    if isinstance(x, bool): return 'да' if x else 'нет'
    if isinstance(x, int): return str(x)
    s = f'{x:.{d}f}'.rstrip('0').rstrip('.') if abs(x) >= 10 ** -d else ('0' if x == 0 else f'{x:.2g}')
    return s.replace('.', ',').replace('-', '−')
def ci(b): return '—' if b.get('ci') is None else f"от {n(b['ci'][0])} до {n(b['ci'][1])}"
def pv(x): return '—' if x is None else ('меньше 0,000001' if x < 5e-7 else f'{x:.6f}'.rstrip('0').rstrip('.').replace('.', ','))   # p в файле результатов округлено до шести знаков
def seeds(b): return '—' if b.get('seeds_plus') is None else f"{b['seeds_plus']} / {b['seeds_minus']} / {b.get('seeds_zero', 0)}"
def tasks(b): return f"{b['tasks_plus']} из {b['tasks_total']}"
out = []
W = out.append
W(f"<!-- сгенерировано report_tables.py из {'facts_pilot.json' if mode == 'pilot' else 'facts.json'}; прогонов {F['runs']}, сидов {F['seeds']} ({F['seed_first']}–{F['seed_last']}) -->\n")

# А. Проверки с вердиктом
W('### А. Проверки с вердиктом\n')
W('| № | Мера | В пилоте (3 сида) | Среднее по сидам | Интервал 95 % | p в сторону ожидания | p в обратную | Сиды: плюс / минус / ноль | Задач со знаком плюс | Вердикт |')
W('|---|---|---|---|---|---|---|---|---|---|')
for num, key, name in (('P1', 'P1a_dose_slope', 'минус наклон завышения показателя по доле экзаменов (T2–T6)'),
                       ('P3', 'P3_truth_ALT50_vs_NOISE50', 'правда лучшего по показателю: ALT_50 − NOISE_50'),
                       ('P4', 'P4_purge_NOISE50_minus_ALT50', 'завышение показателя: NOISE_50 − ALT_50 (T2–T6)'),
                       ('P5', 'P5_popmean_truth_ALT25_vs_FINAL25', 'средняя правда популяции: ALT_25 − FINAL_25')):
    b = F[key]; W(f"| {num} | {name} | {n(FP[key]['mean'])} | {n(b['mean'])} | {ci(b)} | {pv(b['p_up'])} | {pv(b['p_down'])} | {seeds(b)} | {tasks(b)} | {b['verdict']} |")
b = F['P4_purge_NOISE50_minus_ALT50']
if 'within_sens_margin' in b: W(f"\nP4, чувствительность: интервал целиком внутри ±0,02 — {n(b['within_sens_margin'])}.")

# Б. По задачам
W('\n### Б. Те же проверки по задачам (среднее по сидам; в скобках сиды плюс / минус / ноль)\n')
keys = (('P1', 'P1a_dose_slope'), ('P3', 'P3_truth_ALT50_vs_NOISE50'), ('P4', 'P4_purge_NOISE50_minus_ALT50'), ('P5', 'P5_popmean_truth_ALT25_vs_FINAL25'))
W('| Задача | ' + ' | '.join(k for k, _ in keys) + ' |'); W('|---|' + '---|' * len(keys))
for t in ('T1', 'T2', 'T3', 'T4', 'T5', 'T6'):
    row = []
    for _, key in keys:
        x = F[key]['by_task'].get(t); row.append('—' if x is None else f"{n(x['mean'])} ({x['plus']} / {x['minus']} / {x['ties']})")
    W(f'| {t} | ' + ' | '.join(row) + ' |')

# В. Кривая доз
W('\n### В. Кривая доз: доля экзаменов и исход (поздние поколения)\n')
W('| Ветвь | Доля поколений с экзаменом | Свежих меток на прогон | Завышение показателя (T2–T6) | Остаток завышения | Правда рабочей элиты | Правда лучшего по показателю | Средняя правда популяции |')
W('|---|---|---|---|---|---|---|---|')
T = F['tables']
for a, q in (('FIX', '0'), ('ALT_12', '1/8'), ('ALT_25', '1/4'), ('ALT_50', '1/2'), ('ALT_75', '3/4'), ('RND', '1')):
    ex = None if F['excess_share'] is None else F['excess_share'][a]
    W(f"| {a} | {q} | {F['labels_per_run'][a]} | {n(F['dose_W_ind'][a])} | {n(ex)} | {n(F['dose_T_key'][a])} | {n(T['T_ind'][a]['mean'])} | {n(T['mT'][a]['mean'])} |")

# Г. Контроли и расписания
W('\n### Г. Контроли и другие расписания\n')
W('| Ветвь | Свежих меток на прогон | Завышение показателя (T2–T6) | Правда рабочей элиты | Правда лучшего по показателю | Средняя правда популяции | Правда вне диапазона |')
W('|---|---|---|---|---|---|---|')
for a in ('NOISE_25', 'NOISE_50', 'MIX_25', 'MIX_50', 'FINAL_25', 'FINAL_50', 'RND4', 'ALT_6_N64', 'ALT_25_T20'):
    W(f"| {a} | {F['labels_per_run'][a]} | {n(F['W_ind_T2_T6'][a])} | {n(T['T_key'][a]['mean'])} | {n(T['T_ind'][a]['mean'])} | {n(T['mT'][a]['mean'])} | {n(T['T_out'][a]['mean'])} |")

# Д. Описательные меры
W('\n### Д. Описательные меры (без вердикта)\n')
W('| Мера | В пилоте (3 сида) | Среднее по сидам | Интервал 95 % | Сиды: плюс / минус / ноль | Задач со знаком плюс |')
W('|---|---|---|---|---|---|')
for key, name in (('P1b_inner_slope', 'P1b: минус внутренний наклон завышения (ALT_12…ALT_75), T2–T6'),
                  ('P2_exam_gradient_on_inflation', 'P2: градиент отбора по экзамену на завышение при равной правде, ветвь FIX, T2–T6'),
                  ('D_P2_in_ALT50_exam_gens', 'то же в экзаменационных поколениях ALT_50'),
                  ('D_SE_I_full_shift_FIX', 'полный сдвиг завышения при отборе по экзамену, ветвь FIX'),
                  ('D_noise_slope', 'минус наклон завышения через FIX, NOISE_25, NOISE_50'),
                  ('D_purge_NOISE25_minus_ALT25', 'завышение: NOISE_25 − ALT_25'),
                  ('D_truth_ALT25_vs_NOISE25', 'правда лучшего по показателю: ALT_25 − NOISE_25'),
                  ('D_truth_ALT25_vs_MIX25', 'правда: ALT_25 − MIX_25'),
                  ('D_P5_by_T_ind', 'P5 по правде лучшего по показателю: ALT_25 − FINAL_25'),
                  ('D_P5_by_T_key', 'P5 по правде рабочей элиты: ALT_25 − FINAL_25'),
                  ('D_uniq_FINAL25_minus_ALT25', 'число разных программ в популяции (из 300): FINAL_25 − ALT_25')):
    b = F[key]; W(f"| {name} | {n(FP[key]['mean'])} | {n(b['mean'])} | {ci(b)} | {seeds(b)} | {tasks(b)} |")
for key in ('P2_exam_gradient_on_inflation', 'D_P2_in_ALT50_exam_gens'):
    if 'beta_T_mean' in F[key]: W(f"\nГрадиент по правде ({key}): {n(F[key]['beta_T_mean'])}.")
W('\nПо задачам:\n')
dk = (('P1b', 'P1b_inner_slope'), ('P2', 'P2_exam_gradient_on_inflation'), ('полный сдвиг', 'D_SE_I_full_shift_FIX'), ('наклон через NOISE', 'D_noise_slope'), ('NOISE_25 − ALT_25, завышение', 'D_purge_NOISE25_minus_ALT25'))
W('| Задача | ' + ' | '.join(k for k, _ in dk) + ' |'); W('|---|' + '---|' * len(dk))
for t in ('T1', 'T2', 'T3', 'T4', 'T5', 'T6'):
    row = []
    for _, key in dk:
        x = F[key]['by_task'].get(t); row.append('—' if x is None else f"{n(x['mean'])} ({x['plus']} / {x['minus']} / {x['ties']})")
    W(f'| {t} | ' + ' | '.join(row) + ' |')

# Е. Ставки
W('\n### Е. Ставки и калибровка\n')
W('| Ставка | Моя вероятность | Сбылась |'); W('|---|---|---|')
for b in F['bets']: W(f"| {b['id']} | {n(b['p'], 2)} | {'да' if b['outcome'] else 'нет'} |")
s = F['bets_summary']
W(f"\nСбылось {s['came_true']} из {s['n']}; средняя вероятность {n(s['mean_probability'])}; оценка Брайера {n(s['brier'])}; на верной стороне от 0,5 — {s['right_side']} из {s['not_half']}.")
W('\nВеличины ставок B1–B9:\n')
for k, v in F['bets_values'].items():
    W(f"- {k}: " + (', '.join(f'{a} {n(x)}' for a, x in v.items()) if isinstance(v, dict) else n(v)))

# Ж. Незнание и самообман (ИОИ)
W('\n### Ж. Незнание и самообман (среднее по шести задачам)\n')
W('| Ветвь | Незнание | Самообман |'); W('|---|---|---|')
for a in ('FIX', 'ALT_12', 'ALT_25', 'ALT_50', 'ALT_75', 'RND', 'NOISE_25', 'NOISE_50', 'MIX_25', 'MIX_50', 'FINAL_25', 'FINAL_50', 'RND4', 'ALT_6_N64', 'ALT_25_T20'):
    W(f"| {a} | {n(T['ign'][a]['mean'])} | {n(T['dec'][a]['mean'])} |")

# З. Функциональная информация
W(f"\n### З. Функциональная информация: медиана бит рабочей элиты (предел счёта {n(F['fi_limit_bits'], 2)} бита; «>» — за пределом)\n")
W('| Задача | FIX: правда | FIX: заявка | ALT_25: правда | ALT_25: заявка | RND: правда | RND: заявка |'); W('|---|---|---|---|---|---|---|')
def fb(x): return '>' + n(F['fi_limit_bits'], 2) if x is None else n(x, 1)
for t in ('T1', 'T2', 'T3', 'T4', 'T5', 'T6'):
    row = []
    for a in ('FIX', 'ALT_25', 'RND'):
        v = F['fi_bits'].get(f'{t}_{a}')
        row += ['—', '—'] if v is None else [fb(v['truth_bits_median']), fb(v['claim_bits_median'])]
    W(f'| {t} | ' + ' | '.join(row) + ' |')

# И. Приложение: по задачам
for name, title in (('W_ind', 'завышение показателя'), ('T_key', 'правда рабочей элиты'), ('mT', 'средняя правда популяции')):
    W(f'\n### Приложение: {title} по задачам\n')
    W('| Ветвь | T1 | T2 | T3 | T4 | T5 | T6 |'); W('|---|---|---|---|---|---|---|')
    for a, row in T[name].items(): W(f'| {a} | ' + ' | '.join(n(row[t]) for t in ('T1', 'T2', 'T3', 'T4', 'T5', 'T6')) + ' |')
W('\n### Приложение: доля прогонов, где задача решена (правда рабочей элиты в поздних поколениях выше 0,999)\n')
W('| Ветвь | T1 | T2 | T3 | T4 | T5 | T6 |'); W('|---|---|---|---|---|---|---|')
for a, row in F['solved_share'].items(): W(f'| {a} | ' + ' | '.join(n(row[t]) for t in ('T1', 'T2', 'T3', 'T4', 'T5', 'T6')) + ' |')
p = os.path.join(H, 'report_tables_pilot.md' if mode == 'pilot' else 'report_tables.md'); open(p, 'w', encoding='utf-8').write('\n'.join(out) + '\n'); print(p, len(out), 'строк')
