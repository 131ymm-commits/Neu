# SELECT-01: числа итогового отчёта для сверки `ledger.py audit` — выходы analyze обеих выборок без per_task
# (per_task даёт тысячи чисел, и почти любое совпадает случайно) и разность D_N − B_blind пилота 2.
# После совета 33 (описательно): знаки разностей по задачам (лучше / поровну / хуже) и число задач, где D_N отказалась
# всеми 5 голосами (выбор целиком A0), — отдельно от задач, где регрет D_N и A0 просто совпал.
#   python3 report_final_facts.py > final_facts.json
import json
out = {}
for s in ('main', 'rep'):
    a = json.load(open(f'{s}_an_wh.json')); a.pop('per_task', None); out[s] = a
PAIRS = (('D_N', 'B_blind'), ('D_N', 'A0'), ('D_N', 'C_N'), ('D', 'C'))
for s_ in ('main', 'rep'):
    pt = json.load(open(f'{s_}_an_wh.json'))['per_task']
    out[s_]['signs_better_equal_worse'] = {f'{x} − {y}': [sum(pt[t][x] < pt[t][y] for t in pt), sum(pt[t][x] == pt[t][y] for t in pt),
                                                         sum(pt[t][x] > pt[t][y] for t in pt)] for x, y in PAIRS}
    ev = [json.loads(l) for l in open(f'evals/{s_}_eval.complete.jsonl', encoding='utf-8')]
    dn = {}
    for e in ev:
        if e['arm'] == 'D_N' and e['task'] in pt:
            dn.setdefault(e['task'], []).append(e.get('choice'))
    out[s_]['D_N_all_refused_tasks'] = sum(all(c == -1 for c in v) for v in dn.values())
    out[s_]['D_N_worse_than_A0_pct'] = round(100 * out[s_]['signs_better_equal_worse']['D_N − A0'][2] / len(pt))
out['pilot2_D_N_minus_B_blind'] = json.load(open('p2_an_wh.json'))['tests']['D_N']['vs_B_blind']['mean_diff']
print(json.dumps(out, ensure_ascii=False, indent=1))
