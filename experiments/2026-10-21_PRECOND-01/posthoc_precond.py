# PRECOND-01: пост-хок к open_an.json и val_an.json (описательно, вердиктов не меняет). 1 — линейный член модели насыщения (PREREG §4.7, Т8; ERRORS № 94).
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
# пост-хок 2: мощность вопроса 1 (омнибус, 63 степени свободы) и Freedman–Lane для REFUSE при наблюдённых главных действиях.
# Синтетика: 9 задач × 64 клетки, действия = оценки open_an.json (effect_raw), шум — остаток модели главных действий
# (sd с поправкой на степени свободы: N − задачи − 8). Перестановок 2000 на тест, 200 повторов; зерно своё, потоки вопроса 1 не трогаются.
me = json.load(open('open_an.json'))['main_effects']; import prompts_precond as PP
beta = np.array([me[f]['effect_raw'] / 2 for f in PP.F]); N = Y.size
res = Y - A.X @ ((Y.reshape(-1) @ np.tile(A.X, (len(T), 1))) / N); sd = float(np.sqrt((res ** 2).sum() / (N - len(T) - len(PP.F))))
rng = np.random.default_rng(28102026); A.B = 2000; reps, hit_q1, hit_ref = 200, 0, 0
for _ in range(reps):
    Ys = A.X @ beta + rng.normal(0, sd, (len(T), len(A.CELLS))); Ys = Ys - Ys.mean(axis=1, keepdims=True)
    S = float((Ys.mean(axis=0) ** 2).sum())
    Ss = (np.stack([Ys[ti][rng.permuted(np.tile(np.arange(len(A.CELLS)), (A.B, 1)), axis=1)] for ti in range(len(T))]).mean(axis=0) ** 2).sum(axis=1)
    hit_q1 += ((Ss >= S - 1e-12).sum() + 1) / (A.B + 1) < 0.05
    j = PP.F.index('REFUSE'); hit_ref += A.fl_p(Ys, A.X[:, j], np.delete(A.X, j, axis=1), rng)[1] < 0.05
out['power_posthoc'] = dict(note='пост-хок, описательно: мощность при наблюдённых действиях и шуме открытия', resid_sd=round(sd, 3), reps=reps, permutations=A.B,
                            Q1=round(hit_q1 / reps, 3), REFUSE_fl=round(hit_ref / reps, 3))
# пост-хок 3: места клеток по неокруглённому среднему регрету (в open_an.json средние округлены, C44 и C38 там вровень — 0,323)
means = {c: float(Yraw[:, ci].mean()) for ci, c in enumerate(A.CELLS)}; rank = sorted(A.CELLS, key=lambda c: (means[c], A.CELLS.index(c)))
out['rank_unrounded'] = dict(ANCHOR_C44=rank.index('C44') + 1, ALLON_C63=rank.index('C63') + 1, OBS_C12=rank.index('C12') + 1, top6=rank[:6])
# пост-хок 4 (проверка победителя, описательно): разложение отказов по рукам — как refusal_decomposition открытия (Т7).
# Голос с отказом получает регрет A0 своей задачи; вклад отказов = доля × (регрет A0 у отказов − регрет ответивших).
Rv, _, REFv, _, _ = A.load('val', 'evals/val.jsonl'); A0v = A.load.A0R; W = json.load(open('winners.json'))
out['val_refusals'] = {}
for arm in ('OBS', 'MODEL', 'ANCHOR'):
    ks = [k for k in Rv if k[1] == arm]; rf = [k for k in ks if REFv[k]]; an = [k for k in ks if not REFv[k]]
    a0r = st.mean(A0v[k[0]] for k in rf) if rf else None; ar = st.mean(Rv[k] for k in an)
    out['val_refusals'][arm] = dict(votes=len(ks), refused=len(rf), share=round(len(rf) / len(ks), 3), answered_regret=round(ar, 3),
                                    A0_regret_refused=None if a0r is None else round(a0r, 3),
                                    contribution=0.0 if not rf else round(len(rf) / len(ks) * (a0r - ar), 3))
# пост-хок 5 (совет 39, «что проверить первым», описательно): доля отказов на открытии по наличию REFUSE и UNSURE в клетке —
# рост отказов от открытия к проверке идёт от руки (REFUSE × UNSURE) или от задач. По выборам, без правды.
ev = [json.loads(l) for l in open('evals/open.jsonl', encoding='utf-8')]; cnt, tot = {}, {}
for e in ev:
    if e['arm'] not in HP.CELLS: continue
    on = set(HP.CELLS[e['arm']]); k = f'REFUSE={"да" if "REFUSE" in on else "нет"}, UNSURE={"да" if "UNSURE" in on else "нет"}'
    tot[k] = tot.get(k, 0) + 1; cnt[k] = cnt.get(k, 0) + (e['choice'] == -1)
out['open_refusals_by_cell'] = {k: dict(refused=cnt[k], votes=tot[k], share=round(cnt[k] / tot[k], 3)) for k in sorted(tot)}
out['open_refusals_C44'] = sum(e['choice'] == -1 for e in ev if e['arm'] == 'C44')
json.dump(out, open('posthoc_an.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False))
