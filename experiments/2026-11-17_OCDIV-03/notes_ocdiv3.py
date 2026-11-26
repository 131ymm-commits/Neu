#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-03: заметки после данных для REPORT-OCDIV-03.md — разделы «Коротко» (дополнение), «Для главного вопроса», «Что дальше» и
«После данных». Написаны после вывода анализа теста (каркас report_ocdiv3.py закоммичен до данных: 3d958354). Текст мой; числа
подставляются из json анализа тем же форматированием, что в report_ocdiv3.py, — чтобы в тексте не было чисел из памяти. Производные
числа (интервалы сред при 0,0025 / 5, знаки по средам, F на ID, разности с формулой, время заданий) считаются здесь и пишутся в
notes_derived.json — его читает ledger.py audit. Вердиктов и чтения скрипт не меняет.
  python3 notes_ocdiv3.py [ANALYSIS.json]
По умолчанию — gha_out/ocdiv3_sum_test/analysis.json; пишет report_notes.json и notes_derived.json рядом со скриптом.
Время заданий извлечения — только поле seconds через tools/raw_status.filtered (белый список)."""
import glob
import json
import os
import sys

import numpy as np
from scipy.stats import t as student_t

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, X)
import raw_status  # noqa: E402
import ocdiv3 as O3  # noqa: E402   порог доли «без числа» на ID — константа проверки метода (ocdiv2.prepare_id → S.MAX_NONE)

a = sys.argv[1:]
A = json.load(open(os.path.join(ROOT, a[0] if a else 'gha_out/ocdiv3_sum_test/analysis.json'), encoding='utf-8'))
PN = json.load(open(os.path.join(ROOT, 'gha_out/ocdiv3_pilot_n2/pilot.json'), encoding='utf-8'))   # разбор пилота (64471bd4)
PD = json.load(open(os.path.join(X, 'prereg_derived.json'), encoding='utf-8'))                       # числа PREREG (до прогона)
OUT, OUT_DER = os.path.join(X, 'report_notes.json'), os.path.join(X, 'notes_derived.json')
MAXN = O3.W.S.MAX_NONE


def f(x, d=4):                                  # то же, что report_ocdiv3.f
    if x is None or x != x:
        return '—'
    return f'{x:+.{d}f}'.replace('-', '−').replace('.', ',')


def g(x, d=4):                                  # то же, что report_ocdiv3.g
    if x is None or x != x:
        return '—'
    return f'{x:.{d}f}'.replace('.', ',')


def iv(c, d=4):
    return f'[{f(c[0], d)}; {f(c[1], d)}]'


V, M = A['verdicts'], A['marks']
assert A['method']['ok'] and all(V[k] == 'подтверждено' and M[k] == 'общий' for k in ('П1', 'П2', 'П3')), 'тексты написаны под этот исход'
assert A['П2']['reading']['reading'] == 'сверх трудности, видимой во входе'
E = A['envs']
NV = A['method']['valid']
z = A['z_env']
RK = {'П1': 'T4', 'П2': 'T4d', 'П3': 'T4id'}


def short_env(n):
    return n.replace('_p3', '')


env_ci, env_sign = {}, {}
for r, k in RK.items():
    env_ci[r] = {n: [E[n][k]['point'] - z * E[n][k]['sd'], E[n][k]['point'] + z * E[n][k]['sd']] for n in NV}
    env_sign[r] = dict(pos=[n for n in NV if env_ci[r][n][0] > 0], neg=[n for n in NV if env_ci[r][n][1] < 0],
                       zero=[n for n in NV if env_ci[r][n][0] <= 0 <= env_ci[r][n][1]])
pt = {r: {n: E[n][k]['point'] for n in NV} for r, k in RK.items()}
fm, pre = A['formula'], A['formula_pilot_prediction']
diff_pre = {n: fm[n]['T4_observed'] - pre[n]['T4_pred'] for n in NV}
diff_test = {n: fm[n]['T4_observed'] - fm[n]['T4_pred'] for n in NV}
t4_t4d = {n: fm[n]['T4_minus_T4d'] for n in NV}
coinc = {n: E[n]['descr']['совпадение ответов']['point'] for n in NV}
diffic = {n: E[n]['descr']['трудность по входу']['point'] for n in NV}
f_id = {n: E[n]['T4id']['F'] for n in NV}
f0_id = {n: E[n]['T4id']['F0'] for n in NV}
f_ood = {n: E[n]['T4']['F'] for n in NV}
f0_ood = {n: E[n]['T4']['F0'] for n in NV}
auc = {n: E[n]['separation']['auc_dhat_false_major'] for n in NV}
rd = {n: E[n]['read']['diff'] for n in NV}
out_heads = {n: {h: dict(none_frac_id=v['none_frac_id'], id_correct=v['id_correct'], id_wrong=v['id_wrong'])
                 for h, v in E[n]['method'].items() if not v['ok']} for n in NV}
loo1 = A['П1']['leave_one_env_out']['by_env']
loo1_min = min(loo1, key=lambda n: loo1[n]['ci'][0])
secs = []
for p in sorted(glob.glob(os.path.join(ROOT, 'gha_out', 'ocdiv3_test_*', 'answers_*.json'))):
    s = raw_status.filtered(json.load(open(p, encoding='utf-8'))).get('seconds')
    if s is not None:
        secs.append(s)
rx = [n for n in NV if E[n]['extra_tokens']['n_cells']]
pa = A['pairs']
# совет 71, Н3: t по средам (среды как выборка, df = 4) — пост-хок, описательно; порог — квантиль Стьюдента при уровне PREREG на сторону
t_env = {r: float(np.mean(list(pt[r].values())) / (np.std(list(pt[r].values()), ddof=1) / np.sqrt(len(NV)))) for r in RK}
t_thr = float(student_t.ppf(1 - A['level'], len(NV) - 1))
der = dict(t_env=t_env, t_threshold=t_thr, t_df=len(NV) - 1, t_quantile=1 - A['level'], series_confirm=3 * A['level'], series_with_refute=2 * 3 * A['level'],
           source='notes_ocdiv3.py по analysis.json', z_env=z, env_ci=env_ci, env_sign=env_sign,
           env_sign_counts={r: {k: len(v) for k, v in s.items()} for r, s in env_sign.items()},
           t4d_minus_t4_mean=A['П2']['delta'] - A['П1']['delta'], t4_minus_t4d_by_env=t4_t4d,
           t4_minus_t4d_pos=[n for n in NV if t4_t4d[n] > 0], t4_minus_t4d_neg=[n for n in NV if t4_t4d[n] < 0],
           coincidence_by_env=coinc, coincidence_pos=int(sum(coinc[n] > 0 for n in NV)), difficulty_by_env=diffic,
           F_id=f_id, F0_id=f0_id, F_id_min=min(f_id.values()), F_id_max=max(f_id.values()),
           F_ood_min=min(f_ood.values()), F_ood_max=max(f_ood.values()), F0_ood=f0_ood,
           F0_id_min=min(f0_id.values()), F0_id_max=max(f0_id.values()),
           F0_ood_min=min(f0_ood.values()), F0_ood_max=max(f0_ood.values()),
           F_ood_over_F_id={n: f_ood[n] / f_id[n] for n in NV},
           F_ood_over_F_id_min=min(f_ood[n] / f_id[n] for n in NV), F_ood_over_F_id_max=max(f_ood[n] / f_id[n] for n in NV),
           joint_by_env={n: E[n]['descr']['совместность ошибок']['point'] for n in NV},
           formula_obs_minus_pred_pilot_crowd=diff_pre, formula_obs_minus_pred_test_crowd=diff_test,
           auc_min=min(auc.values()), auc_max=max(auc.values()), read_diff_min=min(rd.values()), read_diff_max=max(rd.values()),
           heads_out=out_heads, crowd_size={n: len(E[n]['crowd']) for n in NV},
           loo_p1_min_env=loo1_min, loo_p1_min=loo1[loo1_min],
           pairs_rank=round(pa['p_exact'] * pa['n_structures']),
           extract_seconds_max=max(secs), extract_minutes_max=max(secs) / 60, extract_seconds_min=min(secs), n_answer_files=len(secs),
           extract_minutes_estimate_p1=PD['time_max'] * 2200 / 60, max_none_id=MAXN,
           analysis_seconds=A['seconds'], analysis_minutes=A['seconds'] / 60)
json.dump(der, open(OUT_DER, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

P1, P2, P3 = A['П1'], A['П2'], A['П3']
D = {k: A[f'descr_descr {k}'] for k in ('трудность по входу', 'совместность ошибок', 'совпадение ответов')}
x39 = out_heads['T_X39_p3']
assert list(x39) == ['Qwen2.5-1.5B-Instruct'] and all(not out_heads[n] for n in NV if n != 'T_X39_p3')
q = x39['Qwen2.5-1.5B-Instruct']
neg1 = env_sign['П1']['neg']
assert neg1 == ['T_X49_p3'] and env_sign['П1']['zero'] == ['T_X59_p3'] and len(env_sign['П1']['pos']) == 3
assert env_sign['П2']['zero'] == ['T_X49_p3'] and not env_sign['П2']['neg'] and len(env_sign['П3']['pos']) == 5
c49 = env_ci['П1']['T_X49_p3']
by_env = lambda d: ', '.join(f'{short_env(n)} {f(d[n])}' for n in NV)   # noqa: E731

short = [
    f"**Т4 по средам:** {by_env(pt['П1'])}. Интервал среды при 0,0025 / 5 в T_X49_p3 — {iv(c49)}, в T_X59_p3 накрывает 0. "
    "Среднее пяти сред — не свойство каждой среды. В OCDIV-02 по точкам невырожденных сред было > 0 — 2, < 0 — 1 (C-105).",
    f"**Нуль со стратами по трудности эффекта в среднем не снял:** Т4ᵈ {f(P2['delta'])} против Т4 {f(P1['delta'])}. Страты на тесте трудность "
    f"различают (Н1 — 5 из 5; разность ложного большинства «верхняя − нижняя страта» {g(der['read_diff_min'])}–{g(der['read_diff_max'])}; AUC d̂ → "
    f"ложное большинство {g(der['auc_min'])}–{g(der['auc_max'])}). Член «трудность по входу» Т4 − Т4ᵈ по средам: {by_env(t4_t4d)} — в X19 и X29 "
    "больше нуля, в X49 и X59 меньше (как в пилоте).",
    "**Т4-ID и базы** (совет 71, Н2): специфичность к сдвигу не установлена; на ID трудность от совпадения не отделена (N0 трудность не "
    "сохраняет). "
    f"База другая: на ID F — {g(der['F_id_min'])}–{g(der['F_id_max'])} при F₀ {g(der['F0_id_min'])}–{g(der['F0_id_max'])}, вне диапазона F — "
    f"{g(der['F_ood_min'])}–{g(der['F_ood_max'])}. Описательная разность Т4 − Т4-ID ({f(A['descr_T4 − T4-ID']['delta'])}) сравнивает разности "
    f"при F, различающихся в {g(der['F_ood_over_F_id_min'], 1)}–{g(der['F_ood_over_F_id_max'], 1)} раза, и мерой «где ошибки зависимее» не служит.",
    f"**Толпа.** В T_X39_p3 — 6 голов: Qwen2.5-1.5B не прошла проверку метода по PREREG §4 (доля «без числа» на ID {g(q['none_frac_id'])} > "
    f"{g(MAXN, 2)}); "
    "в остальных средах — 7. В пилоте 2 в X39, X49 и X59 было по 6 голов, поэтому Т4 из формул «по толпе теста» в X49 и X59 отличается от "
    "предсказания до прогона.",
]
main_q = [
    f"**При перестановочном нуле N0 (частоты ошибок голов сохранены) ложное большинство F₀ уже {g(der['F0_ood_min'])}–{g(der['F0_ood_max'])}; "
    f"в T_X49_p3 F₀ > F** (совет 71, Н5). Наблюдаемое F — {g(der['F_ood_min'])}–{g(der['F_ood_max'])}: какой-нибудь неверный ответ набирает не "
    f"меньше голосов, чем верный. Сверх нуля — в среднем этих пяти сред {f(P1['delta'])} (П1). Избыток над N0 трудностью, видимой во входе, не "
    "объясняется (П2 с чтением Н1); трудность, которую признаки входа (c1, n9, u, v) не видят, нуль Nd не исключает.",
    "**Что сохраняют нули (проверено по коду):** счёт идёт по смещениям «ответ − правда» (`ocdiv2.dmat`), N0 и Nd переставляют смещения головы "
    "между задачами (`ocdiv2.permute_cols`). Общая для голов систематическая ошибка с одним и тем же смещением на всех задачах в нуле уже "
    "учтена. Т4 ≠ 0 значит, что смещения голов (и нулевые, то есть верные ответы, и неверные) разложены по задачам согласованнее или "
    "рассогласованнее, чем при перестановке; какая часть — от совпадения неверных смещений, показывает разложение ниже.",
    f"**Где сидит избыток (описательно, разложение по N3; M4 при 0,005):** трудность по входу {f(D['трудность по входу']['delta'])} "
    f"{iv(D['трудность по входу']['ci'])}; совместность ошибок сверх неё {f(D['совместность ошибок']['delta'])} {iv(D['совместность ошибок']['ci'])}; "
    f"совпадение самих неверных ответов {f(D['совпадение ответов']['delta'])} {iv(D['совпадение ответов']['ci'])}. N3 сохраняет, на каких задачах "
    "ошибается каждая голова, и переставляет её неверные смещения внутри страты Nd8, а не по всей среде; «совпадение неверных ответов» — избыток "
    "над совпадением внутри страты (совет 71, Н6). Разложение последовательное: вклады зависят от порядка нулей N0 → Nd8 → N3. В среднем избыток "
    "даёт совпадение неверных смещений на одной задаче. "
    f"«Совместность ошибок» по средам разного знака: {by_env(der['joint_by_env'])}. «Совпадение ответов» больше нуля в {der['coincidence_pos']} "
    f"средах из 5 (T_X49_p3 — {f(coinc['T_X49_p3'])}). Механизм совпадения — объяснение не проверялось.",
    f"**Не свойство сдвига:** на ID ложное большинство редко (F до {g(der['F_id_max'])}), но тоже чаще нуля N0 (Т4-ID {f(P3['delta'])}). N0 "
    "трудность задач не сохраняет, поэтому на ID вклад трудности от совпадения ответов не отделён. Точка Т4-ID может быть смещена отбором толпы "
    "по ID (PREREG §4, Н5) — довод, не проверено.",
    f"**Т4 из формул ступени 1 DISTILL-01** (условная независимость, неверные ответы без совпадений) до прогона попала в X19, X29 и X39 с "
    f"ошибкой {f(diff_pre['T_X19_p3'])}, {f(diff_pre['T_X29_p3'])}, {f(diff_pre['T_X39_p3'])}, а в X49 и X59 ошиблась по знаку "
    f"({f(diff_pre['T_X49_p3'])}, {f(diff_pre['T_X59_p3'])}). Там же отрицателен член трудности. Совпадение с ERRORS № 197 (при совпадающих "
    "неверных ответах G другого вида) — довод, не проверено.",
]
nxt = [
    "**Порядок (совет 71; запуск — по слову автора).** (1) Гипотеза OCDIV-04 с первичной мерой коммитится первой: мера фиксируется до того, как "
    "её смотрят на данных OCDIV-03 (предупреждение скептика). (2) Пост-хок разбор на GitHub Actions по готовым ответам OCDIV-03 (описательно, "
    "бесплатно): нуль со стратами по узору переносов из операндов (только вход) и положительный контроль N3 — искусственные головы с известной "
    "ошибкой переноса в заданном разряде. Разбор меру не выбирает и в её мощность не входит. (3) Пилот OCDIV-04 на свежих зёрнах: мощность и "
    "размер вброса — по пилоту, без чисел по памяти.",
    "**OCDIV-04 (проект — советом):** первичная мера — F − F₀ при нуле со стратами по узору переносов из операндов; Т4(N0) — вторичная; Nd8 — "
    "вторичная (d̂ вне диапазона может хуже различать трудность — довод скептика). Мера скептика — «вне диапазона минус ID» той же величины "
    "внутри каждой среды. Правило из двух частей: интервал для среднего и знак в каждой среде; мощность — по разбросу между средами, а не по "
    "повторам бутстрепа. Отрицательный контроль — пары одного производителя против пар разных. Assert в коде: модели d̂ учатся только на пилоте.",
    "**Реестр** (совет 71, Н10): «установлено» — ничему. C-105 — новой записью: зависимость сверх частот голов (Т4(N0), трудность не учтена) в "
    "среднем пяти сред > 0, знак по средам разный; специфичность для «вне диапазона» не установлена — контроль П3 показал эффект и на ID (вес 0 "
    "бит, не «опровергнуто»). Новая запись по OCDIV-03 — «подтверждено» о среднем этих пяти сред; F − F₀(N3) — только гипотеза для OCDIV-04.",
]
notes = [
    f"**Детерминизм проверен на 3 из 7 голов, в одной среде (T_X29_p3)** (совет 71, Н7): повторы на других процессорах — ответы совпали во "
    f"всех 2200 задачах каждого, наибольшая |Δ logp| — {g(max(x['max_abs_dlogp'] for x in A['repeat_check']), 6)}.",
    f"**t по средам** (среды как выборка, df = {der['t_df']}; пост-хок, описательно, вердикт не меняет; совет 71, Н3): П1 {g(t_env['П1'], 2)}, "
    f"П2 {g(t_env['П2'], 2)}, П3 {g(t_env['П3'], 2)} при пороге t({g(1 - A['level'], 4)}; {der['t_df']}) = {g(t_thr, 3)} (scipy). Вердикт П1 "
    "относится к этим пяти средам и на другие среды не переносится; у П2 t тоже ниже порога. Интервал M4 учитывает только разброс внутри сред, "
    "проверка «без одной среды» тоже.",
    f"**Общий ложный уровень серии** (совет 71, Н4; PREREG §7): ложное «подтверждено» — не больше {g(der['series_confirm'], 4)} "
    f"(3 × {g(A['level'], 4)}, Бонферрони), с ложным «опровергнуто» — не больше {g(der['series_with_refute'], 3)}. Номинально: перенос M4 на "
    f"{g(A['level'], 4)} для среднего пяти сред не проверен.",
    "**Модели d̂ обучены только на пилоте** (совет 71, Н8; проверено по коду и хешам): `ocdiv3.test` учит модели на сборке пилота 2 до чтения "
    "ответов теста и останавливается, если веса не совпали с разбором пилота (`models_checked: True` в analysis.json); разбор пилота (64471bd4) "
    "закоммичен раньше запуска теста (86227345); семь файлов ответов пилота 2 «тысяч» — в `prereg_hashes3.json`, анализ сверил хеши (78 файлов). "
    "В OCDIV-04 — assert в коде.",
    "**Сверка ключевых чисел по точному ключу** (совет 71, Н9): `check_report3.py` сравнивает числа вердиктов, границы интервалов сред, t и "
    "диапазоны F и F₀ в отчёте со значениями по путям в analysis.json и notes_derived.json (поле env_ci — границы интервалов сред), лог — "
    "`check_report3.log`; `ledger.py audit` — 0 «не найдено».",
    f"**Прибор:** {E[rx[0]]['extra_tokens']['n_cells']} числовых ответов толпы с лишними токенами — все в {rx[0]}; пересчёт с ними как «без числа»: "
    f"Т4 {f(E[rx[0]]['extra_tokens']['recount']['T4'])} (основной счёт {f(pt['П1'][rx[0]])}), Т4ᵈ "
    f"{f(E[rx[0]]['extra_tokens']['recount']['T4d'])} ({f(pt['П2'][rx[0]])}). Вердикт — по основному счёту.",
    f"**Предохранитель П1 держится, но с малым запасом:** наименьшая нижняя граница — без {loo1_min}: {f(loo1[loo1_min]['delta'])} "
    f"{iv(loo1[loo1_min]['ci'])}.",
    f"**Время:** наибольшее задание извлечения — {g(der['extract_seconds_max'], 1)} с ({g(der['extract_minutes_max'], 1)} мин; оценка по p = 1 — "
    f"{g(der['extract_minutes_estimate_p1'], 1)} мин, перенос на p = 3 не проверялся); анализ — {g(der['analysis_seconds'], 1)} с ({g(der['analysis_minutes'], 1)} мин; оценка «порядка "
    "часа» была пропорцией). Все 38 заданий и анализ прошли с первого раза; отступлений от PREREG нет.",
    f"**Пары производителей:** контраст {f(pa['observed'])}, точное p = {g(pa['p_exact'])} ({der['pairs_rank']} из {pa['n_structures']} структур; "
    f"в пилоте {f(PN['pairs']['observed'])}, p = {g(PN['pairs']['p_exact'])}) — от нуля не отличено.",
]
CJ = json.load(open(os.path.join(ROOT, 'docs/council/2026-11-17_OCDIV-03-report_session71.json'), encoding='utf-8'))
votes = CJ['votes']
n_for = sum(v['vote'] == 'за' for v in votes)
assert CJ['status'] == 'принято единогласно' and n_for == len(votes) == 4 and CJ['timer']['over_s'] == 0
council = dict(title='Совет 71 — оценка отчёта (18.11.2026)', items=[
    f"**{CJ['status'][0].upper() + CJ['status'][1:]}: {n_for} из {len(votes)} «за» после правок «нужно»;** перебора времени нет. Стенограмма — "
    "`docs/council/2026-11-17_OCDIV-03-report_session71.md`. Первый запуск совета остановлен замком времени до первой головы (ERRORS № 199).",
    "**Правки «нужно» Н1–Н10 внесены:** Н1 — «подтверждено» как «в среднем этих пяти сред» со знаком по средам, «общий» — только имя пометки "
    "PREREG; Н2 — П3 как контроль неспецифичности (провал для заявки «именно вне диапазона»); Н3 — t по средам, пост-хок; Н4 — общий ложный "
    "уровень серии; Н5 — строка о F₀ при нуле N0; Н6 — определение N3, порядок нулей, развилки; Н7 — детерминизм 3 из 7 голов в одной среде; "
    "Н8 — модели d̂ только на пилоте; Н9 — сверка чисел по точному ключу; Н10 — реестр без «установлено».",
    "**Несогласия:** как назвать П3 — скептик: «провал контроля», формалист: «контроль выполнил задачу, эффект неспецифичен»; запись совмещает "
    "обе. Детерминизм 3 из 7 — правка «нужно» большинством 3 против 1 (интуит: «можно»). Филогения голов по общим неверным смещениям (интуит) — "
    "только описание; опора на текстологию (по памяти) — 0 бит, опорой отчёта не служит.",
    "**Для OCDIV-04 (в «Что дальше»):** правило из двух частей (среднее и знак в каждой среде), мощность по разбросу между средами; первичная "
    "мера — F − F₀ при нуле со стратами по узору переносов из операндов; мера фиксируется до того, как её смотрят на данных OCDIV-03; "
    "положительный контроль N3 — искусственные головы; отрицательный — пары производителей.",
])
json.dump(dict(short=short, main_q=main_q, next=nxt, notes=notes, council=council), open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('записано', OUT, OUT_DER)
