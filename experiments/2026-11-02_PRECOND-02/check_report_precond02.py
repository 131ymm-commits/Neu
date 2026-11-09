# PRECOND-02: адресная сверка чисел REPORT_final.md с interim_an.json, final_facts.json, prior_refuse.json и power_precond02.json
# (по образцу check_final_precond.py PRECOND-01). Каждое число строится из json в формате отчёта и ищется в тексте дословно.
import json, sys
ia, F, pr0, pw = (json.load(open(f)) for f in ('interim_an.json', 'final_facts.json', 'prior_refuse.json', 'power_precond02.json'))
o1 = json.load(open('../2026-10-21_PRECOND-01/open_an.json'))
T = open('REPORT_final.md', encoding='utf-8').read()
def r(x): s = f'{x:.3f}'.rstrip('0').rstrip('.') if isinstance(x, float) else str(x); return s.replace('-', '−').replace('.', ',')
def sg(x): return ('+' if x > 0 else '') + r(x)
def ci(c): return f'{r(c[0])} … {r(c[1])}'
def big(n): n = round(n); return f'{n:,}'.replace(',', ' ') if n >= 10000 else str(n)
def sci(p): mn, e = f'{p:.1e}'.split('e'); return f'{mn.replace(".", ",")}·10' + str(int(e)).translate(str.maketrans('-0123456789', '⁻⁰¹²³⁴⁵⁶⁷⁸⁹'))
p, d, b = ia['primary'], ia['describe'], ia['bounds']
assert ia['decision'] == 'остановить: эффективность' and ia['defined'] and not ia['excluded_eps'] and ia['n_tasks'] == F['n_tasks'] == 180
need = [f'Действие REFUSE — {r(p["effect_REFUSE"])} (95 % t-ДИ {ci(p["effect_ci95"])})', f't {r(F["t"])} (df {p["gain"]["df"]})',
        f'одностороннее p {sci(F["p_exact"])}', f'границе {b["p1_nominal"]:.4f}'.replace('.', ','), f'c1 {r(round(b["c1"], 3))}', f'c2 {r(round(b["c2"], 3))}',
        f'(p {b["p2_nominal"]:.4f})'.replace('.', ','), f'g = NOREF − ANCHOR: {sg(p["gain"]["mean"])} (ДИ {ci(p["gain"]["ci95"])})', f'sd разностей {r(round(F["sd"], 3))}',
        f'«{ia["decision"]}»', f'на открытии PRECOND-01 ({r(round(o1["main_effects"]["REFUSE"]["effect_raw"], 3))})']
need.append(f'({", ".join(r(v["D_minus_C"]["mean"] if abs(v["D_minus_C"]["mean"] * 1000 - round(v["D_minus_C"]["mean"] * 1000)) < 1e-9 else round(v["D_minus_C"]["mean"], 3)) for v in pr0.values())};')
A_, N_ = d['ANCHOR'], d['NOREF']
assert A_['not_ok'] == N_['not_ok'] == 0 and set(d['vote_status']) == {'ok', 'refused'} and not d['input_span']['flag']
need += [f'| ANCHOR (D_N) | {r(A_["regret"])} | {r(A_["refusal_share"])} | {sg(A_["refusal_contribution"])} | {r(A_["answered_regret"])} | {big(A_["out_per_call"])} |',
         f'| NOREF (C_N) | {r(N_["regret"])} | 0 | 0 | {r(N_["answered_regret"])} | {big(N_["out_per_call"])} |',
         f'| {r(d["A0_no_calls"])} |', f'«ок» {d["vote_status"]["ok"]}, отказов {d["vote_status"]["refused"]}',
         f'в {r(A_["refusal_share"])} голосов ({A_["refusals"]} из {A_["votes"]})', f'Вклад отказов в регрет {sg(A_["refusal_contribution"])}',
         f'длиннее на {round(A_["out_per_call"] - N_["out_per_call"])} токенов', f'не больше {d["input_span"]["max"]} токенов']
E = F['expectations']; need += [f'сбылось: {r(E["E4"]["value"])}', f'сбылось: {sg(E["E5"]["value"]).replace(",3", ",3")}', f'механически выполнено: {r(E["E3"]["value"])}']
assert E['E1']['outcome'] and E['E2']['outcome'] and E['E4']['outcome'] and E['E5']['outcome'] and E['E3']['outcome'] is None and E['E3']['holds']
o = F['order']
for k, label in (('prereg', 'регистрация'), ('pools_B', 'пулы этапов A и B'), ('jobs_A', 'задания оценщиков A'), ('evals_A', 'выборы A'),
                 ('interim', 'промежуточный анализ'), ('salt_A', 'соль A опубликована')):
    c, at = o[k]; need.append(f'| {label} | {c} | ' + (f'{at[8:10]}.{at[5:7]} ' if k in ('prereg', 'pools_B', 'jobs_A', 'evals_A') else '') + f'{at[11:19]} |')
need += [f'| серверное событие пуша | — | {o["push_time"][11:]} |', f'| первая запись правды | — | {o["truth_first_mtime"][11:19]} |', o['evals_sha_event'][:8]]
assert o['evals_sha_event'] == o['evals_sha_disk']
C = F['calls']
for j, label in (('A_exec', 'исполнитель, этап A'), ('B_exec', 'исполнитель, этап B'), ('A_eval', 'оценщики, этап A')):
    x = C[j]; assert list(x['finals']) == ['годный'] and x['models'] == ['claude-opus-5-5'] and x['started_unrecorded'] == 0
    need.append(f'| {label} | {x["finals"]["годный"]} | {x["attempts"]} | {x["no_answer_attempts"]} | {big(x["out"])} |')
need += [f'Выход теста — {big(F["test_out"])} токенов', f'(пилот — {big(C["pilot_exec"]["out"] + C["pilot_eval"]["out"])})', f'{C["A_eval"]["segments"]} сегментами',
         f'у всех {F["streams"]["совпал"]} записей']
assert F['streams'] == {'совпал': sum(C[j]['attempts'] for j in ('A_exec', 'B_exec', 'A_eval'))}
H = F['heads_audit']; nh = sum(h['calls'] for h in H)
assert all(h['tools'] == ['StructuredOutput'] and not h['mcp'] and h['git_instructions_off'] and not h['git_snapshot_possible'] and list(h['model']) == ['claude-opus-5-5'] for h in H)
need += [f'во всех {nh} вызовах', f'пилот {C["pilot_exec"]["attempts"] + C["pilot_eval"]["attempts"]}']
sb = F['support_bits']; need += [f'Вес опоры C-041 — {r(sb["total"])} бита', f'{r(sb["base_hypothesis_neu"])};', f'PRECOND-02 — {r(sb["precond02"])}, это log₂({r(sb["power"])} / {r(sb["false_level"])})']
d3 = pw['designs']['180/360']; need += [f'максимум {r(d3["max_out_mln"])} млн']
K = F['council41']; e3 = K['e3_threshold']; npw = K['next_power']   # совет 41 (09.11)
assert K['no_answer'] == {'всего': 5, 'usage 0': 5, 'повтор годный': 5} and len(K['init_hashes']) == 1 and K['exec_jobs_arm_hits'] == 0
assert K['pools_B'] == {'files': 180, 'commits': {o['pools_B'][0]: 180}} and K['attempts_all'] == nh + 5
need += [f'не меньше {r(e3["plan"])} по sd плана (PREREG §5); ≈{r(e3["observed"])} по наблюдённому sd', f'было бы {r(K["bits_alt"]["C-041 (открытие, точечно)"]["bits"])}',
         f'при мощности {r(K["bits_alt"]["C-041 (открытие, точечно)"]["power"])}', f'(init {K["init_hashes"][0]}…) одна у всех {K["attempts_all"]} попыток',
         f'модель — у {nh} вызовов с итогом', f'все {K["pools_B"]["files"]} пулов — один коммит {o["pools_B"][0]}',
         f'{r(npw["left_n180"])}–{r(npw["engineer_n180"])} на 180 задачах B, около {r(npw["engineer_n360"])} на 360', f'по sd плана {r(round(npw["sd"], 3))} (§8)',
         f'Остановка сберегла {C["A_eval"]["finals"]["годный"]} вызовов оценщиков B']
miss = [x for x in need if x not in T]
print(f'проверено фраз: {len(need)}; не найдено: {len(miss)}')
[print('  НЕТ:', x) for x in miss]
sys.exit(1 if miss else 0)
