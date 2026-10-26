# THINK-01: адресная сверка чисел REPORT_final.md с rep_an.json, main_an.json, rep_facts.json и final_facts.json (по образцу check_main_think.py).
# Каждое число строится из json в формате отчёта и ищется в тексте дословно; формулировки, которые совет 35 запретил, ищутся тоже.
import json, sys
m, a = json.load(open('main_an.json')), json.load(open('rep_an.json')); f, F = json.load(open('rep_facts.json')), json.load(open('final_facts.json'))
T = open('REPORT_final.md', encoding='utf-8').read()
def r(x): s = f'{x:.3f}'.rstrip('0').rstrip('.') if isinstance(x, float) else str(x); return s.replace('-', '−').replace('.', ',')
def ci(c): return f'{r(c[0])} … {r(c[1])}'
def big(n): return f'{n:,}'.replace(',', ' ') if n >= 10000 else str(n)
SUP = str.maketrans('-0123456789', '⁻⁰¹²³⁴⁵⁶⁷⁸⁹')
def sci(p, d=1): mn, e = f'{p:.{d}e}'.split('e'); return f'{mn.replace(".", ",")}·10{str(int(e)).translate(SUP)}'
def pp(p): return sci(p) if p < 0.001 else (f'{p:.4f}'.replace('.', ',') if p < 0.01 else r(p))
need = []
for k in a['primary']:
    for name, x in (('основная', m), ('повтор', a)):
        v = x['primary'][k]
        need.append(f'| {k} | {name} | {r(v["mean"])} | {ci(v["ci95"])} | ≤ {sci(f["p_floor"], 0)} | {" / ".join(map(str, v["wins_losses_ties"]))} | '
                    f'{big(v["out_H_1"])} и {big(v["out_rival"])} | {"да" if v["counts"] else "нет"} |')
assert all(all(v) for v in F['established'].values())                     # «установлено»: засчитано в обеих выборках
need += [f'perm_le = {int(x)}' for x in list(f['perm_le'].values()) + list(json.load(open('main_facts.json'))['perm_le'].values())][:1]
need += [r(f['out_ratio_B_blind']), r(f['out_ratio_D_N']), r(f['regret_ratio_B_blind']), r(f['out_ratio_H_c'])]
for arm in ('A0', 'B_blind', 'U_N', 'P_N', 'C_N', 'D_N', 'H_1', 'H_3', 'H_c'):
    need += [r(m['mean_regret'][arm]['mean']), r(a['mean_regret'][arm]['mean']), r(a['mean_regret'][arm]['median'])]
for arm in ('B_blind', 'U_N', 'P_N', 'C_N', 'D_N', 'H_1', 'H_c', 'H'): need.append(big(a['tokens_per_task'][arm]['out']))
s1b = {k: v for k, v in a['secondary']['S1b_equal_budget_system'].items() if k != 'curve_m_1_5'}
need += [f'| {k} | {v["m"]} | {big(v["out_subset"])} | {r(v["mean"])} | {ci(v["ci95"])} | {v["outcome"]} |' for k, v in s1b.items()]
need.append(f'«{a["program_hypothesis"]}»')
s1 = a['secondary']['S1_system_of_deep_heads']; need += [r(v['mean']) for v in s1.values()] + [ci(s1['H_3 − H_1']['ci95']), ci(s1['H_1 − C_N']['ci95'])]
need.append(r(m['secondary']['S1_system_of_deep_heads']['H_3 − H_1']['mean']))
need += [f'| {arm} | {z} | {b} |' for arm, (z, b) in f['zero_and_bad'].items()]
s2 = a['secondary']['S2_mechanism']
need += [f'| {arm} | {big(v["mean_out_all"])} | {r(v["mean_vote_regret_valid"])} |' for arm, v in s2['per_arm'].items()] + [r(s2['per_arm']['D_N']['refusal_share'])]
need += [f'{"+" if v["coef"] > 0 else ""}{r(v["coef"])} ({ci(v["ci95"])})' for v in s2['equal_length_model'].values()]
need += [f'{"+" if v["mean"] > 0 else ""}{r(v["mean"])} ({ci(v["ci95"])})' for v in s2['plurality_vs_C_N'].values()]
need.append(r(m['secondary']['S2_mechanism']['plurality_vs_C_N']['D_N − C_N']['mean']))
s3 = a['secondary']['S3_self_assessment']
need += [r(s3[k]) for k in ('mean_p_best', 'accuracy_lenient', 'accuracy_strict', 'brier', 'brier_constant_rate', 'ece_5bins', 'auroc_p_best_correct')]
need += [f'{r(s3["H_c_minus_H_1"]["mean"])} ({ci(s3["H_c_minus_H_1"]["ci95"])})', f'на {r(-f["s3_overconfidence"])}', f'на {r(f["s3_gap_strict"])}']
s4 = a['secondary']['S4_refusal_informativeness']; need += [f'— {s4["tasks_with_refusal"]}', r(s4['auroc_refusal_vs_C_N_difficulty'])]
need += [f'{r(v["mean"])} ({ci(v["ci95"])}; p {pp(v["p"])})' for v in a['secondary']['S5_select01_replication'].values()]
E = F['expectations']; need += [f'| {k} |' for k in E]
assert [k for k, v in E.items() if not v] == ['P6']                         # в таблице «не сбылось» — только P6
pa = lambda x, arm: x['secondary']['S2_mechanism']['per_arm'][arm]['mean_out_all']
need.append(f'({pa(m, "D_N")} и {pa(m, "U_N")}; {pa(a, "D_N")} и {pa(a, "U_N")})')
need += [f'коммит {f["push_after"]} — {f["commit_at"][:19]}, за {f["commit_before_push_s"]} с до серверного события GitHub о пуше {f["push_time"]}',
         f['eval_sha_on_disk'], f'{f["last_done"]["high"][:19]} (high)', f'{f["last_done"]["medium"][:19]} (medium)']
assert f['eval_sha_in_commit'] == f['eval_sha_on_disk']
assert F['rep_finals'] == {'годный': 1800} and F['rep_no_answer_attempts'] == 3 and F['rep_models'] == ['claude-opus-5-5'] and F['rep_cli'] == ['2.1.294']
need += [f'все {F["rep_finals"]["годный"]} итогов «годные»', f'{F["rep_no_answer_attempts"]} попытки «нет ответа»', F['rep_models'][0], f'CLI {F["rep_cli"][0]}', F['rep_binary_sha256'][0][:8]]
# совет 36: проверки повтора (rep_checks.json), хеш зафиксированного main_an.json, ворота S1b в «Итоге»
import hashlib
C = json.load(open('rep_checks.json')); assert C['differences'] == 0 and C['rederive']['equals_commit_57c1f60'] and C['rederive']['streams_mismatch'] == 0
need += [f'numpy {C["numpy_b"]}', f'numpy {C["numpy_a"]}', f'расхождений {C["differences"]}', f'у всех {C["rederive"]["streams_match"]} вызовов', C['rederive']['evals_sha256_rederived'][:8],
         hashlib.sha256(open('main_an.json', 'rb').read()).hexdigest()[:16]]
gate = [k for k, v in s1b.items() if v['budget_matched'] and not v['descriptive']]
need += [f'одна рука из четырёх ({gate[0]})', f'{r(a["mean_regret"]["P_N"]["mean"])} против C_N {r(a["mean_regret"]["C_N"]["mean"])}'] if len(gate) == 1 else ['ворота: не одна рука']
miss = [n for n in need if n not in T]
bad = [b for b in ('нижняя граница', 'Механизм выигрыша', 'механизм — длина', 'недоуверенна', 'Раз главное', 'При равном бюджете все системы',
                   'объясняется длиной', 'При равной длине ответа') if b in T]
print(f'проверено фраз: {len(need)}; не найдено: {len(miss)}; запрещённых найдено: {len(bad)}')
[print('  НЕТ:', x) for x in miss]; [print('  ЗАПРЕЩЕНО:', b) for b in bad]
sys.exit(1 if miss or bad else 0)
