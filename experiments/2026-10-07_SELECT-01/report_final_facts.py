# SELECT-01: числа итогового отчёта для сверки `ledger.py audit` — выходы analyze обеих выборок без per_task
# (per_task даёт тысячи чисел, и почти любое совпадает случайно) и разность D_N − B_blind пилота 2.
#   python3 report_final_facts.py > final_facts.json
import json
out = {}
for s in ('main', 'rep'):
    a = json.load(open(f'{s}_an_wh.json')); a.pop('per_task', None); out[s] = a
out['pilot2_D_N_minus_B_blind'] = json.load(open('p2_an_wh.json'))['tests']['D_N']['vs_B_blind']['mean_diff']
print(json.dumps(out, ensure_ascii=False, indent=1))
