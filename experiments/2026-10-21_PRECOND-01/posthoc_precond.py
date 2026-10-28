# PRECOND-01: дополнение к open_an.json — линейный член модели насыщения (PREREG §4.7, Т8; ERRORS № 94).
# analyze_precond.py выводит только коэффициент при k² и флаг «k² > 0», а по PREREG насыщение (убывающая польза) засчитывается,
# только если линейный член отрицателен. Модель та же: регрет ~ k + k² внутри задач, k — число включённых ингредиентов клетки.
# Описательно, вердиктов не меняет. Правда открытия опубликована (salts/open_salt.txt); пересчёт — по README в salts/.
#   python3 posthoc_precond.py  →  posthoc_an.json
import json, statistics as st
import numpy as np
import analyze_precond as A, harness_precond as HP
R = A.load('open', 'evals/open.jsonl')[0]
T = sorted({t for (t, a, i) in R}); Yraw = np.array([[R.get((t, c, 0), 1.0) for c in A.CELLS] for t in T]); Y = Yraw - Yraw.mean(axis=1, keepdims=True)
k = np.array([len(HP.CELLS[c]) for c in A.CELLS], dtype=float); kc = k - k.mean(); k2 = kc ** 2 - (kc ** 2).mean()
co = [np.linalg.lstsq(np.column_stack([kc, k2]), Y[ti], rcond=None)[0] for ti in range(len(T))]
q1, q2 = [float(c[0]) for c in co], [float(c[1]) for c in co]
out = dict(note='линейный член насыщения (Т8); код анализа его не выводил — ERRORS № 94', n_tasks=len(T),
           linear=A.t_ci(q1), k2=A.t_ci(q2), k2_equals_open_an=A.t_ci(q2) == json.load(open('open_an.json'))['saturation_descriptive']['k2'],
           saturation_by_prereg=bool(st.mean(q2) > 0 and st.mean(q1) < 0))
json.dump(out, open('posthoc_an.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False))
