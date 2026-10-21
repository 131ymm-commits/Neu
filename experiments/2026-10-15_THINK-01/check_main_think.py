# THINK-01: адресная сверка чисел REPORT_main.md с main_an.json и main_facts.json (по образцу SELECT-01 check_final.py).
# Каждое число строится из json в формате отчёта и ищется в тексте дословно.
import json, sys
a = json.load(open('main_an.json')); f = json.load(open('main_facts.json')); T = open('REPORT_main.md', encoding='utf-8').read()
def r(x): s = f'{x:.3f}'.rstrip('0').rstrip('.') if isinstance(x, float) else str(x); return s.replace('-', '−').replace('.', ',')
def ci(c): return f'{r(c[0])} … {r(c[1])}'
def big(n): return f'{n:,}'.replace(',', ' ') if n >= 10000 else str(n)
need = []
for k, v in a['primary'].items():
    need += [f'| {k} | {r(v["mean"])} | {ci(v["ci95"])} |', ' / '.join(map(str, v['wins_losses_ties'])), f'{big(v["out_H_1"])} и {big(v["out_rival"])}']
for arm in ('A0', 'B_blind', 'U_N', 'P_N', 'C_N', 'D_N', 'H_1', 'H_3', 'H_c'):
    need.append(r(a['mean_regret'][arm]['mean']))
for arm in ('B_blind', 'U_N', 'P_N', 'C_N', 'D_N', 'H_1', 'H_c'):
    need.append(big(a['tokens_per_task'][arm]['out']))
need.append(big(a['tokens_per_task']['H']['out']))
for k, v in a['secondary']['S1b_equal_budget_system'].items():
    if k != 'curve_m_1_5': need.append(f'| {k} | {v["m"]} | {big(v["out_subset"])} | {r(v["mean"])} | {ci(v["ci95"])} |')
for k, v in a['secondary']['S1_system_of_deep_heads'].items(): need.append(r(v['mean']))
need.append(ci(a['secondary']['S1_system_of_deep_heads']['H_3 − H_1']['ci95']))
s2 = a['secondary']['S2_mechanism']
for arm, v in s2['per_arm'].items(): need += [f'| {arm} | {big(v["mean_out_all"])} | {r(v["mean_vote_regret_valid"])} |']
need.append(r(s2['per_arm']['D_N']['refusal_share']))
for k, v in s2['equal_length_model'].items(): need.append(f'{"+" if v["coef"] > 0 else ""}{r(v["coef"])} ({ci(v["ci95"])})')
for k, v in s2['plurality_vs_C_N'].items(): need.append(f'{"+" if v["mean"] > 0 else ""}{r(v["mean"])} ({ci(v["ci95"])})')
s3 = a['secondary']['S3_self_assessment']
need += [r(s3[k]) for k in ('mean_p_best', 'accuracy_lenient', 'accuracy_strict', 'brier', 'brier_constant_rate', 'ece_5bins', 'auroc_p_best_correct')]
need.append(f'{r(s3["H_c_minus_H_1"]["mean"])} ({ci(s3["H_c_minus_H_1"]["ci95"])})')
s4 = a['secondary']['S4_refusal_informativeness']; need += [f'— {s4["tasks_with_refusal"]}', r(s4['auroc_refusal_vs_C_N_difficulty'])]
for k, v in a['secondary']['S5_select01_replication'].items(): need.append(f'{r(v["mean"])} ({ci(v["ci95"])}; p {r(v["p"]) if v["p"] >= 0.001 else f"{v[chr(112)]:.4f}".replace(".", ",")})')
need += [r(f['out_ratio_B_blind']), r(f['out_ratio_D_N']), r(f['out_ratio_H_c']), r(f['regret_ratio_B_blind']), r(-f['s3_overconfidence']),
         f['push_time'], f['push_after'], f['first_start'][:19], f['last_start'][:19]]
# совет 35: p как предел разрешения Монте-Карло, запас выхода H_1 в S1b, доли регрета 0 и > 0,5, строгая точность, пауза по run_log, хеш в коммите
m_, e_ = f"{f['p_floor']:.0e}".split('e'); pf = f"{m_}·10{str(int(e_)).translate(str.maketrans('-0123456789', '⁻⁰¹²³⁴⁵⁶⁷⁸⁹'))}"
need += [f'p ≤ {pf}', f'| ≤ {pf} |'] + [f'perm_le = {int(v)}' for v in f['perm_le'].values()]
s1b = {k: v for k, v in a['secondary']['S1b_equal_budget_system'].items() if k != 'curve_m_1_5'}; mg = f['s1b_margin']
assert all(-v['mean'] - mg[k]['slope_correction'] > 0 for k, v in s1b.items())            # «вывод держится по каждой строке»
need += [f'| +{r(round(100 * mg[k]["extra_out"], 1))} % | {r(mg[k]["slope_correction"])} |' for k in s1b]
ex = [x['extra_out'] for x in mg.values()]; sc = [x['slope_correction'] for x in mg.values()]
need += [f'{round(100 * min(ex))}–{round(100 * max(ex))} %', f'{r(min(sc))}–{r(max(sc))}',
         f'{big(a["tokens_per_task"]["H_1"]["out"])} против {big(min(v["out_subset"] for v in s1b.values()))}–{big(max(v["out_subset"] for v in s1b.values()))}']
tested = [k for k, v in s1b.items() if not v['descriptive']]; low = min(tested, key=lambda k: -s1b[k]['mean'] - mg[k]['slope_correction'])
need += [f'у {low}: разность {r(s1b[low]["mean"])} при поправке {r(mg[low]["slope_correction"])}',
         f'Холм по {({4: "четырём", 5: "пяти"})[len(tested)]} сравнениям'] + [f'«{s1b[k]["outcome"]}»' for k in tested]
need += [f'у описательной {k} — {r(v["mean"])} при поправке {r(mg[k]["slope_correction"])}' for k, v in s1b.items() if v['descriptive']]
need += [f'| {arm} | {z} | {b} |' for arm, (z, b) in f['zero_and_bad'].items()] + [f'на {r(f["s3_gap_strict"])}', f'разрыв {r(f["s3_gap_strict"])}']
need.append(f'«{a["program_hypothesis"]}»')
pa = f['pause']; assert pa['high'] == pa['medium'] and pa['high']['from_event'] == 'пауза' and pa['high']['to_event'] == 'старт'
need += [f'«пауза» {pa["high"]["from_at"][:19]} до записи «старт» {pa["high"]["to_at"][:19]}', f'`{pa["high"]["from_reason"].split()[0]}`',
         f'{f["last_done"]["high"][:19]} (high)', f'{f["last_done"]["medium"][:19]} (medium)',
         f'коммит **{f["push_after"]}** — {f["commit_at"][:19]}, за {f["commit_before_push_s"]} с до серверного события GitHub о пуше {f["push_time"]}']
assert f['eval_sha_in_commit'] == f['eval_sha_on_disk']
need += [f['eval_sha_on_disk'], f'git show {f["push_after"]}:./evals/main_eval.jsonl | sha256sum']
miss = [n for n in need if n not in T]
# формулировки первой редакции, которые совет 35 велел убрать (ERRORS № 89)
bad = [b for b in ('нижняя граница', 'Механизм выигрыша', 'механизм — длина', 'недоуверенна', 'Раз главное', 'Холм по пяти',
                   'При равном бюджете все системы', 'S1b — системы голов при равном бюджете', 'стояла пауза') if b in T]
print(f'проверено фраз: {len(need)}; не найдено: {len(miss)}; запрещённых найдено: {len(bad)}')
[print('  НЕТ:', m) for m in miss]; [print('  ЗАПРЕЩЕНО:', b) for b in bad]
sys.exit(1 if miss or bad else 0)
