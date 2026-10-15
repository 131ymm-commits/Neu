# SELECT-01: адресная сверка чисел REPORT_final.md с json. `ledger.py audit` здесь мало что доказывает: в отчёте
# в основном трёхзначные доли, а в данных их столько, что совпадение почти любого значения случайно.
# Скрипт строит из json строки таблиц и фразы отчёта и ищет их в тексте дословно; печатает ненайденные.
#   python3 check_final.py   (код выхода 1, если что-то не найдено)
import json, sys
R = open('REPORT_final.md', encoding='utf-8').read()
J = lambda p: json.load(open(p))
m, r = J('main_an_wh.json'), J('rep_an_wh.json')
po, ms, rs, rf, rl = J('pooled_wh.json')['pooled'], J('main_secondary.json'), J('rep_secondary.json'), J('rep_facts.json'), J('rep_losses.json')
mf = J('main_facts.json')

def f(v, d=None):            # число как в отчёте: «−», десятичная запятая, без хвостовых нулей
    v = round(v, d) if d is not None else v
    s = str(int(abs(v))) if float(v).is_integer() else str(abs(v))
    return ('−' if v < 0 else '') + s.replace('.', ',')
ci = lambda c: f'{f(c[0])} … {f(c[1])}'
pf = lambda p: format(p, '.2g').replace('.', ',') if p > 1e-4 else '≈1,0·10⁻⁵'   # p в таблицах — две значащие цифры
th = lambda n: f'{n:,}'.replace(',', ' ')
names = {'E': 'E (случайный выбор)', 'A0': 'A0 (лучший по заявке)', 'A': 'A (= B_zayavka[0])', 'B_zayavka': 'B_zayavka',
         'B_blind': 'B_blind', 'C': 'C (= C_N[0])', 'C_N': 'C_N', 'D': 'D (= D_N[0])', 'D_N': 'D_N'}
calls = dict(E=0, A0=0, A=1, B_zayavka=5, B_blind=12, C=1, C_N=5, D=1, D_N=5)
t, tm = r['tests'], m['tests']
need = [f"| {names[a]} | {calls[a]} | {f(m['mean_regret'][a]['mean'])} | {f(r['mean_regret'][a]['mean'])} |" for a in names]
for x in ('D_N', 'C_N'):
    for k, lab in (('vs_B_blind', 'B_blind'), ('vs_A0', 'A0')):
        need.append(f"| {x} − {lab} | {f(t[x][k]['mean_diff'])} | {ci(t[x][k]['ci95'])} | {pf(t[x][k]['p'])} |")
for key, lab in (('D_N − B_blind', 'D_N − B_blind'), ('D_N − A0', 'D_N − A0'), ('C_N − B_blind', 'C_N − B_blind'), ('C_N − A0', 'C_N − A0')):
    need.append(f"| {lab} | {f(po[key]['mean'])} | {ci(po[key]['ci95'])} |")
sp = lambda s, k: f"{f(s[k]['mean'])} (ДИ {ci(s[k]['ci95'])})"
need += [f"| D_N − C_N | {sp(ms, 'D_N_minus_C_N')} | {sp(rs, 'D_N_minus_C_N')} |", f"| D − C | {sp(ms, 'D_minus_C')} | {sp(rs, 'D_minus_C')} |"]
tok = r['tokens']
need += [f"{a} — {th(tok[a]['inp'])} и {th(tok[a]['out'])}" for a in ('B_blind', 'D_N', 'C_N')]
need += [f"на {f(-t['D_N']['vs_B_blind']['mean_diff'])} (95 % ДИ {ci(t['D_N']['vs_B_blind']['ci95'])}",
         f"на {f(-t['D_N']['vs_A0']['mean_diff'])} (ДИ {ci(t['D_N']['vs_A0']['ci95'])}, p {f(t['D_N']['vs_A0']['p'], 4)})",
         f"p против A0 = {f(t['D_N']['vs_A0']['p'], 4)}",
         f"регрет {f(r['mean_regret']['B_blind']['mean'])} против {f(m['mean_regret']['B_blind']['mean'])}",
         f"{f(m['mean_regret']['D_N']['mean'])} → {f(r['mean_regret']['D_N']['mean'])}",
         f"({f(m['mean_regret']['A0']['mean'])} и {f(r['mean_regret']['A0']['mean'])})",
         f"{f(tm['D_N']['vs_A0']['mean_diff'])} → {f(t['D_N']['vs_A0']['mean_diff'])}"]
d = rf['per_task_diff_vs_B_blind']
need += [f"меньше нуля на {d['D_N']['neg']} задачах, ноль на {d['D_N']['zero']}, больше нуля на {d['D_N']['pos']}; SD {f(d['D_N']['sd'])}",
         f"C_N − B_blind: {d['C_N']['neg']} / {d['C_N']['zero']} / {d['C_N']['pos']}",
         f"Без 5 самых отрицательных задач {f(rs['D_N_minus_B_blind']['without_5_most_negative']['mean'])}",
         f"На {rs['D_N_minus_B_blind']['tasks_with_D_N_refusal']['n']} задачах с отказом D_N ({rs['D_N_refusals']['votes']} отказа) {f(rs['D_N_minus_B_blind']['tasks_with_D_N_refusal']['mean'])}",
         f"на {rs['D_N_minus_B_blind']['tasks_without_D_N_refusal']['n']} без отказа {f(rs['D_N_minus_B_blind']['tasks_without_D_N_refusal']['mean'])}",
         f"{rf['finals']} вызова с итогом: {rf['finals_exec']} исполнителя и {rf['finals_eval']} оценщиков",
         f"Ожиданий лимита — {rf['limit_waits']} ({rl['by_arm']['B_blind']['ожиданий_лимита']} у B_blind, {rl['by_arm']['D_N']['ожиданий_лимита']} у D_N)",
         f"медиана {rf['call_seconds_median']} с, максимум {rf['call_seconds_max']} с",
         f"выход {th(rf['out_tokens'])}, вход {th(rf['inp_tokens'])}", f"${f(rf['list_cost_usd'])}",
         f"init один ({rf['init_variants'][0]}…), модель {rf['models'][0]}, effort {rf['efforts'][0]}",
         f"p_upper {f(t['A_vs_A0_TOST']['p_upper'], 3)}, p_lower {f(t['A_vs_A0_TOST']['p_lower'], 3)}, выбор совпал в {f(t['A_vs_A0_TOST']['agree_share'])}",
         f"+{f(t['A_vs_B_zayavka']['mean_diff'])}, p {f(t['A_vs_B_zayavka']['p'], 3)}",
         f"Спирмен {f(r['secondary']['spearman_claim_truth'])}, AUROC сомнений {f(r['secondary']['doubt_auroc'])} (в основной — {f(m['secondary']['spearman_claim_truth'])} и {f(m['secondary']['doubt_auroc'])})",
         ', '.join(f"+{f(r['secondary']['goodhart_gap_by_k'][k])} при k = {k}" for k in ('1', '2', '4', '8')),
         f"(+{f(m['secondary']['goodhart_gap_by_k']['1'], 0)} → +{f(m['secondary']['goodhart_gap_by_k']['8'], 0)})",
         f"D — {r['secondary']['refusals']['D']} из 99 вызовов, D_N — {r['secondary']['refusals']['D_N']} из 495",
         f"на {rf['D_N_equal_A0_tasks']} задачах из 99",
         ', '.join(str(v) for v in rs['truth_best_shown_position'].values()) + ' раз',
         f"B_blind — {rs['choice_shown_position']['B_blind']['1']} из {sum(rs['choice_shown_position']['B_blind'].values())} голосов",
         f"на {rf['D_N_over_C_N_out_pct']} % в повторе и на {mf['D_N_over_C_N_out_pct']} % в основной"]
ff, act = J('final_facts.json'), J('rep_push_activity.json')['event']   # после совета 33
sg = lambda s_, k: ' / '.join(map(str, ff[s_]['signs_better_equal_worse'][k]))
need += [f"| {k} | {sg('main', k)} | {sg('rep', k)} |" for k in ('D_N − A0', 'D_N − B_blind', 'D_N − C_N', 'D − C')]
need += [f"На {ff['main']['D_N_worse_than_A0_pct']} % задач основной выборки и на {ff['rep']['D_N_worse_than_A0_pct']} % повтора D_N хуже A0",
         f"ни на одной задаче ({ff['main']['D_N_all_refused_tasks']} в обеих выборках)" if ff['main']['D_N_all_refused_tasks'] == ff['rep']['D_N_all_refused_tasks'] == 0 else 'ОШИБКА: полные отказы не 0',
         f"Пуш выборов 16a4b06 — {act['timestamp'][11:]}" if act['after'].startswith('16a4b06') else 'ОШИБКА: событие пуша не 16a4b06',
         f"p = ({round(r['tests']['D_N']['vs_B_blind']['p'] * 200001) - 1} + 1)/(200 000 + 1)"]
sa = J('selfassess_posthoc.json')   # пост-хок 15.10
need += [f"AUROC {f(sa['main']['difficulty_C_N_votes']['auroc_refusal_vs_difficulty'])} и {f(sa['rep']['difficulty_C_N_votes']['auroc_refusal_vs_difficulty'])} по голосам C_N, "
         f"{f(sa['main']['difficulty_B_blind_votes']['auroc_refusal_vs_difficulty'])} и {f(sa['rep']['difficulty_B_blind_votes']['auroc_refusal_vs_difficulty'])} по голосам B_blind",
         f"основная выборка: {f(sa['main']['D_N_answers_minus_C_N_votes']['refusal_tasks']['mean'])} и {f(sa['main']['D_N_answers_minus_C_N_votes']['other_tasks']['mean'])}",
         f"повтор: {f(sa['rep']['D_N_answers_minus_C_N_votes']['refusal_tasks']['mean'])} и {f(sa['rep']['D_N_answers_minus_C_N_votes']['other_tasks']['mean'])}"]
tp = J('thinking_posthoc.json')   # пост-хок 2, 15.10
lm = [tp[s_][a]['long_minus_short_regret'] for s_ in ('main', 'rep') for a in ('B_blind', 'B_zayavka', 'C_N', 'D_N')]
sp = [tp[s_][a]['within_task_spearman_out_regret'] for s_ in ('main', 'rep') for a in ('B_blind', 'B_zayavka', 'C_N', 'D_N')]
eq = lambda s_: tp[s_]['D_N_vs_C_N_at_equal_length']
need += [f"от {f(max(lm))} до {f(min(lm))}, Спирмен «длина ↔ регрет» внутри задачи — от {f(max(sp))} до {f(min(sp))}",
         f"Коэффициент D_N: +{f(eq('main')['coef_D_N'])} (ДИ {ci(eq('main')['ci95_D_N'])}) в основной выборке, +{f(eq('rep')['coef_D_N'])} (ДИ {ci(eq('rep')['ci95_D_N'])}) в повторе",
         f"Коэффициент ln(выход): {f(eq('main')['coef_ln_out'])} и {f(eq('rep')['coef_ln_out'])}",
         f"(средний выход голоса {tp['main']['D_N']['mean_out']} и {tp['rep']['D_N']['mean_out']} токенов против {tp['main']['C_N']['mean_out']} и {tp['rep']['C_N']['mean_out']} у C_N)"]
miss = [s for s in need if s not in R]
print(f'проверено фраз: {len(need)}; не найдено: {len(miss)}')
for s in miss:
    print('  НЕТ:', s)
sys.exit(1 if miss else 0)
