# PRECOND-02: разбор пилота (WH 9301–9310, вне теста) — то же, что промежуточный анализ, без решения: выигрыш g = NOREF − ANCHOR по задачам,
# sd для расчёта мощности, отказы, длина, ответившие голоса (после воздействия), разброс входа одинаковых промптов (чистый контекст).
#   python3 pilot_precond02.py  →  pilot_an.json
import json
import analyze_precond02 as A
from analyze_precond import t_ci
L = A.load('pilot', 'evals/pilot.jsonl'); g = A.gains(L)
out = dict(n_tasks=len(g), excluded_eps=L['excl'], primary=dict(gain=t_ci(g), effect_REFUSE=round(-sum(g) / len(g), 3)),
           per_task={t: round(x, 3) for t, x in zip(L['T'], g)}, describe=A.describe(L))
json.dump(out, open('pilot_an.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
