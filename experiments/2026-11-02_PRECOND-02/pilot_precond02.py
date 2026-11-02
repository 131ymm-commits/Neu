# PRECOND-02: разбор пилота (WH 9301–9310, вне теста) — то же, что промежуточный анализ, без решения: выигрыш g = NOREF − ANCHOR по задачам,
# sd для расчёта мощности, отказы, длина, ответившие голоса (после воздействия), разброс входа одинаковых промптов (чистый контекст).
#   python3 pilot_precond02.py  →  pilot_an.json
import json
import analyze_precond02 as A
from analyze_precond import t_ci
L = A.load('pilot', 'evals/pilot.jsonl'); g = A.gains(L)
import statistics as st
out = dict(n_tasks=len(g), excluded_eps=L['excl'], primary=dict(gain=dict(t_ci(g), sd=round(st.stdev(g), 4)), effect_REFUSE=round(-sum(g) / len(g), 3)),
           per_task={t: round(x, 3) for t, x in zip(L['T'], g)}, describe=A.describe(L))
# положительный контроль чистоты: средний вход ANCHOR в проверке победителя PRECOND-01 (со снимком git) против пилота, при близкой длине промпта
v1 = [json.loads(l) for l in open('../2026-10-21_PRECOND-01/evals/val.jsonl')]; pv = [json.loads(l) for l in open('evals/pilot.jsonl')]
plen = lambda f: st.mean(len(json.loads(l)['prompt']) for l in open(f) if '|ANCHOR|0' in l)
out['ctx_control'] = dict(precond01_val_anchor_inp=round(st.mean(e['inp'] for e in v1 if e['arm'] == 'ANCHOR')),
                          pilot_anchor_inp=round(st.mean(e['inp'] for e in pv if e['arm'] == 'ANCHOR')),
                          precond01_val_anchor_prompt_chars=round(plen('../2026-10-21_PRECOND-01/run/val_eval_medium_jobs.jsonl')),
                          pilot_anchor_prompt_chars=round(plen('run/pilot_eval_jobs.jsonl')))
json.dump(out, open('pilot_an.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
