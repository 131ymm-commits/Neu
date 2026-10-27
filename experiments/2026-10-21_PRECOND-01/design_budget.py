# PRECOND-01: объём и цена вариантов основного опыта по двум пилотам (арифметика над pilot_analysis.json и pilot_high_analysis.json).
#   python3 design_budget.py  →  design_budget.json
import json, math
m, h = json.load(open('pilot_analysis.json')), json.load(open('pilot_high_analysis.json'))
sd_m = round(m['sd_resid'] * math.sqrt(m['n'] / ((6 - 1) * (16 - 1))), 3)   # пилот medium: pstdev → поправка на df = (задачи − 1)(предусловия − 1)
sd_h = h['high']['sd_resid_df']; out_m, out_h = m['out_per_call'], h['high']['out_per_call']; K = 64
def tasks_for(n): return math.ceil(n / K)
nA = math.ceil((2 * sd_m / 0.05) ** 2); tA = tasks_for(nA)                  # A: главные действия на medium, SE 0,05
nB = math.ceil(4 * (sd_m ** 2 + sd_h ** 2) / 0.05 ** 2); tB = tasks_for(nB) # B: взаимодействие effort × ингредиент, SE 0,05
val = 50 * 3 * 5                                                             # проверка победителя: 50 новых задач × 3 руки × 5 голосов, medium
budget = dict(
    sd_medium_df=sd_m, sd_high_df=sd_h, out_medium=out_m, out_high=out_h,
    A=dict(tasks=tA, calls_medium=tA * K, calls_high_reference=tA * 2, exec=tA, se_main=round(2 * sd_m / math.sqrt(tA * K), 3),
           out_tokens_m=round((tA * K * out_m + tA * 2 * out_h) / 1e6, 1)),
    B=dict(tasks=tB, calls_per_level=tB * K, exec=tB, se_interaction=round(2 * math.sqrt((sd_m ** 2 + sd_h ** 2) / (tB * K)), 3),
           out_tokens_m=round(tB * K * (out_m + out_h) / 1e6, 1)),
    validation=dict(calls=val, out_tokens_m=round(val * out_m / 1e6, 1)),
)
json.dump(budget, open('design_budget.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(budget, ensure_ascii=False, indent=1))
