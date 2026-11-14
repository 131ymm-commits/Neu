#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка REPORT-OCCOR-01.md: текст — мой, числа — из run/analysis.json, run/facts_occor.json, analysis_pilot.json, power.json,
pilot/analysis_test_rules_on_pilot.json тем же форматированием, каким их сверяет ledger.py audit."""
import json
import os
import sys

X = sys.argv[1]
J = lambda p: json.load(open(os.path.join(X, p), encoding='utf-8'))  # noqa: E731
r, fa, p, pw, pr = J('run/analysis.json'), J('run/facts_occor.json'), J('analysis_pilot.json'), J('power.json'), J('pilot/analysis_test_rules_on_pilot.json')
E = r['evaluators']


def n(x, d=3, sign=False):
    s = f'{abs(x):.{d}f}'.replace('.', ',')
    if x < 0 and float(s.replace(',', '.')) != 0:
        return '−' + s
    return ('+' if sign and x > 0 else '') + s


def ci(e, d=4):
    return f"[{n(e['ci'][0], d, True)}; {n(e['ci'][1], d, True)}]"


def perc(e, d=4):
    return f"[{n(e['ci_percentile'][0], d, True)}; {n(e['ci_percentile'][1], d, True)}]"


R1, R2, R3, R4 = (r[k] for k in ('R1', 'R2', 'R3', 'R4'))
dec = r['descr_R1_decomposition']
t_la, t_lc = r['descr_top10_sel_LR-AGREE−AGREE'], r['descr_top10_sel_LR-AGREE−CONF']
ph = fa['posthoc_R3_decomposition']
dd, dc = r['dose_descr'], r['dose_descr_contrast']
d2 = r['dose_dedup_as_clone_descr']
cf = r['crossfit_descr']
co = r['lr_coef_groups_descr']
acc = r['accuracy']
cnt = r['method']['counts']
min_cnt = min(min(v['id_correct'], v['id_wrong'], v['ood_correct'], v['ood_wrong']) for v in cnt.values())
ties = [v['tie_frac'] for v in E.values()]
sec = 2571.5
NAMES = {'AGREE': 'AGREE (согласие голов)', 'NB-AGREE': 'NB-AGREE (попарно, наивный Байес)', 'LR-AGREE': 'LR-AGREE (попарно, регрессия)',
         'NB-IND': 'NB-IND (надёжность голов без пар)', 'FAM-AGREE': 'FAM-AGREE (голос на семейство)', 'CONF': 'CONF (уверенность головы)'}
L = []
a = L.append
a('# OCCOR-01 «ОЦЕНЩИК-КОРРЕЛЯЦИЯ» — отчёт (14.11.2026)')
a('')
a('Главный вопрос Neu — оценщик, который не обманывается под давлением отбора. OCCOR-01 спрашивал: можно ли выучить на задачах с правдой от кода (ID), кто из голов с кем ошибается одинаково, и снять этим самообман согласия голов там, где правды нет (OOD).')
a('- **Предрегистрация — коммит c258bb3e** (`PREREG-OCCOR-01.md`). Первый коммит файла 117df8b9 — черновик для совета 54.')
a(f"- **Прогон** — Kaggle, Tesla T4, извлечение {n(sec, 1)} с.")
a(f"  - 9 голов Pythia, из них 4 клона (чекпойнты pythia-2.8b).")
a(f"  - {r['n_id'] + r['n_ood']} задач теста: {r['n_id']} ID и {r['n_ood']} OOD. Сырой вывод закоммичен до анализа (da8060ac).")
a(f"  - Хеши сверены перед анализом. Анализ — 615 с, {r['B']} и {r['BD']} повторов.")
a('- **Числа** — из `run/analysis.json`; производные и пост-хок — из `run/facts_occor.json` (`facts_occor.py`).')
a('')
a('## Итог')
a(f"**Вердикт кода — «{r['verdict']}».** Проверки метода пройдены. Совет 55 принял отчёт единогласно с правками формулировок, они внесены (`docs/council/2026-11-14_OCCOR-01-report_session55.md`).")
a(f"- **Выученное согласие лучше простого (R1).** ИОИ LR-AGREE {n(E['LR-AGREE']['ioi'])} против {n(E['AGREE']['ioi'])} у AGREE: Δ {n(R1['delta'], 4)}, ДИ BC 99,5 % {ci(R1)}.")
a(f"  - Все {r['B']} повторов бутстрепа < 0.")
a('  - LR-AGREE — логистическая регрессия по совпадениям ответа головы с каждой другой головой, обученная на ID.')
a('- **По правилу PREREG §5 вывод — «оценщик скромнее», а не «распознаёт общие ошибки».**')
a(f"  - ΔC {n(dec['dC']['delta'], 4)}, ДИ 99 % {ci(dec['dC'])}; ΔT {n(dec['dT']['delta'], 4, True)}, ДИ BC {ci(dec['dT'])}.")
a(f"  - Доля C — {n(dec['share_C'])}, у порога 0,5. На пилоте было {n(pr['descr_R1_decomposition']['share_C'])}; интервал у доли не считался.")
a(f"  - Доля повторов с ΔT < 0 — {n(dec['dT']['share_below_0'], 4)}, процентильный интервал ΔT {perc(dec['dT'])}. Вклад точности не исключён, доминирование C не установлено.")
a(f"- **LR-AGREE лучше NB-IND (R3).** NB-IND знает надёжность голов, но не попарную структуру. ИОИ {n(E['LR-AGREE']['ioi'])} против {n(E['NB-IND']['ioi'])}: Δ {n(R3['delta'], 4)}, ДИ {ci(R3)}.")
a('  - Это преимущество над NB-IND, а не «специфичность к общим ошибкам» (совет 54).')
a(f"  - Подтверждён при мощности 0,182: величина эффекта, вероятно, завышена (проклятие победителя).")
a(f"  - Пост-хок: и здесь выигрыш почти весь от C (доля {n(ph['share_C'], 2)}, без интервала).")
a(f"- **NB-AGREE против AGREE (R2) — не решено:** Δ {n(R2['delta'], 4)}, ДИ {ci(R2)}. Находка разведки на свежих данных не подтвердилась и не опровергнута.")
a(f"- **Доза клонов (R4) — не решено:** Δ_LR(4) − Δ_LR(1) = {n(R4['delta'], 4)}, ДИ {ci(R4)}.")
a(f"  - Описательно, по всем составам, Δ_LR растёт с числом клонов: {'; '.join(n(dd[k]['delta_LR-AGREE'], 4) for k in ('1', '2', '3', '4'))}.")
a(f"  - У NB-IND такого роста нет: контраст {n(dc['NB-IND'], 4)}.")
a(f"- **Под жёстким отбором отличия от AGREE не видно** (описательно, вес 0). Верхние 10 % выбранных ответов — {fa['top10_sel_n']} задач OOD.")
a(f"  - Самообман: LR-AGREE {n(E['LR-AGREE']['top10_sel']['deception'])}, AGREE {n(E['AGREE']['top10_sel']['deception'])}; разность {n(t_la['delta'], 4)}, ДИ BC 99 % {ci(t_la)} при z₀ {n(t_la['z0'], 3, True)}, процентильный {perc(t_la)}.")
a('  - Снижение самообмана примерно до 0,05–0,09 не исключено.')
a(f"  - Надёжно описательно одно: у CONF самообман {n(E['CONF']['top10_sel']['deception'])}, LR-AGREE обманывается на {n(t_lc['delta'])} больше. ДИ BC {ci(t_lc)} при z₀ {n(t_lc['z0'], 3, True)}, процентильный {perc(t_lc)}.")
a('')
a('| оценщик | T | C | незнание | самообман | ИОИ | верхние 10 % выбранных: точность / заявка / самообман |')
a('|---|---|---|---|---|---|---|')
for e in ('LR-AGREE', 'FAM-AGREE', 'CONF', 'NB-IND', 'NB-AGREE', 'AGREE'):
    v = E[e]
    s = v['top10_sel']
    a(f"| {NAMES[e]} | {n(v['T'])} | {n(v['C'])} | {n(v['ignorance'])} | {n(v['deception'])} | {n(v['ioi'])} | {n(s['accuracy'])} / {n(s['claim'])} / {n(s['deception'])} |")
a('')
a('## 1. Прогон')
a('- **Точность голов (ID / OOD):**')
for k, v in acc.items():
    a(f"  - {k} — {n(v['id'])} / {n(v['ood'])};")
a(f"- Все девять голов загружены на видеокарту. У каждой на ID и на OOD не меньше {min_cnt} верных и {min_cnt} неверных ответов (порог 20). Ответов без числа нет.")
a(f"- Ничьих при выборе головы — {n(min(ties), 4)}–{n(max(ties), 4)}.")
a('- **Повтор пилота.** Задача `neu-occor-pilot-p100` получила T4: Kaggle не выполнил запрос P100.')
a('  - Ответы и logp всех 11 голов совпали с пилотом полностью (`pilot_p100/out/`).')
a('  - Это повтор на той же площадке, а не сверка площадок.')
a('')
a('## 2. Вердикты по PREREG (§5)')
a(f"- **R1 — подтверждено.** Δ_LR = {n(R1['delta'], 4)}, ДИ BC {ci(R1)}; процентильный {n(R1['ci_percentile'][0], 4, True)}…{n(R1['ci_percentile'][1], 4, True)}; z₀ {n(R1['z0'], 3, True)}.")
a(f"  - Хвосты: за верхней (решающей) границей — {R1['tails']['n_above_hi']} повтор из {r['B']}, за нижней — {R1['tails']['n_below_lo']}.")
a(f"  - Обе половины повторов дают «подтверждено» ({n(R1['tails']['halves'][0][1], 4, True)} и {n(R1['tails']['halves'][1][1], 4, True)} — верхние границы).")
a('  - Решающая граница BC опирается на один повтор, как и предупреждал совет 54: номинальный уровень 0,0025 здесь — оценка Монте-Карло.')
a(f"  - Вердикт держат процентильный интервал {perc(R1)}, доля повторов ниже 0 (все {r['B']}) и согласие половин, а не сама граница BC.")
a(f"- **R2 — не решено.** Δ_NB = {n(R2['delta'], 4)}, ДИ {ci(R2)}.")
a(f"- **R3 — подтверждено.** Δ = {n(R3['delta'], 4)}, ДИ {ci(R3)}.")
a(f"  - Хвосты: {R3['tails']['n_below_lo']} и {R3['tails']['n_above_hi']}. Обе половины — «подтверждено». Доля повторов < 0 — {n(R3['share_below_0'], 4)}.")
a('  - Подтверждён при мощности 0,182: величина эффекта, вероятно, завышена. Вес по формуле не пересчитывается — мощность берётся из PREREG.')
a('  - Неспецифичная альтернатива не проверена: LR-AGREE может отзываться на сам сдвиг ID → OOD (вне диапазона меньше совпадений), а не на устройство общих ошибок. Кросс-подгонка её не проверяет — её части лежат внутри ID. Контроль — та же модель на перемешанных парах (опись).')
a(f"- **R4 — не решено.** Δ_LR(4) − Δ_LR(1) = {n(R4['delta'], 4)}, ДИ {ci(R4)} по закреплённым составам (12 и 5). Хвосты {R4['tails']['n_below_lo']} и {R4['tails']['n_above_hi']}.")
a('- **Защита LR:** повторов, где у головы в выборке ID один класс, нет ни в одном бутстрепе.')
a('- Ложное «подтверждено» по серии из четырёх правил — не выше 0,01.')
a('')
a('## 3. Ожидания (PREREG §7)')
a('| № | ожидание | вероятность | исход |')
a('|---|---|---|---|')
ex = [('E1', 'R1 подтверждено', '0,65', 'да'), ('E2', 'R2 подтверждено', '0,07', 'нет'), ('E3', 'R3 подтверждено', '0,18', 'да'),
      ('E4', 'R4 подтверждено', '0,10', 'нет'), ('E5', 'проверки метода пройдены', '0,95', 'да'),
      ('E6', f"точечная Δ_LR < 0 ({n(R1['delta'], 4)})", '0,85', 'да'),
      ('E7', f"верхние 10 % выбранных: самообман LR-AGREE больше, чем у CONF ({n(E['LR-AGREE']['top10_sel']['deception'])} против {n(E['CONF']['top10_sel']['deception'])})", '0,80', 'да')]
for row in ex:
    a('| ' + ' | '.join(row) + ' |')
a('- E3 — исход вопреки низкой мощности (0,182). E2 и E4 — «не решено», в рамках ожиданий.')
a('')
a('## 4. Описательно (вес 0, без вердикта)')
a(f"- **Разложение R1** (PREREG §5; при самообмане > 0 у обоих ΔИОИ = −2ΔT + ΔC): ΔT {n(dec['dT']['delta'], 4, True)} {ci(dec['dT'])}, ΔC {n(dec['dC']['delta'], 4)} {ci(dec['dC'])}, доля C {n(dec['share_C'])}.")
a(f"- **Пост-хок** (записан после данных, вердикт не меняет; без интервала): разложение R3 — ΔT {n(ph['dT'], 4, True)}, ΔC {n(ph['dC'], 4)}, доля C {n(ph['share_C'], 2)}.")
a(f"- **Верхние 10 % выбранных ответов** ({fa['top10_sel_n']} задач):")
sel_dec = ', '.join(e + ' ' + n(E[e]['top10_sel']['deception']) for e in E)
a(f"  - самообман: {sel_dec};")
a(f"  - граничный блок ничьих у AGREE — {E['AGREE']['top10_sel']['boundary_block']} задач, вошёл дробно;")
a(f"  - по всем парам «голова × задача» картина та же: AGREE {n(E['AGREE']['top10_all']['deception'])}, LR-AGREE {n(E['LR-AGREE']['top10_all']['deception'])}, CONF {n(E['CONF']['top10_all']['deception'])}.")
a('- **Прочие разности ИОИ** (ДИ BC 99 %):')
for key, lab in (('descr_LR−CONF', 'LR-AGREE − CONF'), ('descr_AGREE−CONF', 'AGREE − CONF'), ('descr_LR−FAM', 'LR-AGREE − FAM-AGREE'),
                 ('descr_NB−FAM', 'NB-AGREE − FAM-AGREE'), ('descr_NB−NB-IND', 'NB-AGREE − NB-IND')):
    a(f"  - {lab}: {n(r[key]['delta'], 4, True)} {ci(r[key])};")
a(f"- **Доза по всем составам** (k = 1…4: {', '.join(str(dd[k]['n_crowds']) for k in ('1', '2', '3', '4'))} составов):")
for e, lab in (('LR-AGREE', 'Δ_LR'), ('NB-AGREE', 'Δ_NB'), ('NB-IND', 'Δ_IND')):
    a(f"  - {lab}: {'; '.join(n(dd[k][f'delta_{e}'], 4) for k in ('1', '2', '3', '4'))}; контраст 4 − 1 — {n(dc[e], 4, True)};")
a(f"  - контраст FAM-AGREE {n(dc['FAM-AGREE'], 4)}, CONF {n(dc['CONF'], 4)} (разности с AGREE).")
a(f"- **Доза «deduped = клон»** (5 «клонов», 4 не-клона; {', '.join(str(d2['dose'][k]['n_crowds']) for k in ('1', '2', '3', '4'))} составов): Δ_LR {'; '.join(n(d2['dose'][k]['delta_LR-AGREE'], 4) for k in ('1', '2', '3', '4'))}; контраст LR {n(d2['contrast']['LR-AGREE'], 4)}, NB {n(d2['contrast']['NB-AGREE'], 4)}, NB-IND {n(d2['contrast']['NB-IND'], 4, True)}.")
a(f"- **Кросс-подгонка** (5 частей ID, только точка): ИОИ LR-AGREE {n(cf['evaluators']['LR-AGREE']['ioi'], 4)}, NB-AGREE {n(cf['evaluators']['NB-AGREE']['ioi'], 4)}, NB-IND {n(cf['evaluators']['NB-IND']['ioi'], 4)}; R1 {n(cf['deltas']['R1'], 4)}, R3 {n(cf['deltas']['R3'], 4)}.")
a(f"  - Верхние 10 %: LR-AGREE {n(cf['evaluators']['LR-AGREE']['top10_sel']['deception'], 4)}, AGREE {n(cf['evaluators']['AGREE']['top10_sel']['deception'], 4)}, CONF {n(cf['evaluators']['CONF']['top10_sel']['deception'], 4)}.")
a(f"  - Средний вывод R1 кросс-подгонка не меняет ({n(cf['deltas']['R1'], 4)} против {n(R1['delta'], 4)}). На верхушке по точке LR-AGREE {n(cf['evaluators']['LR-AGREE']['top10_sel']['deception'])} против {n(cf['evaluators']['AGREE']['top10_sel']['deception'])} у AGREE, интервала нет: это тот сдвиг, о котором предупреждал PREREG §8.")
a(f"- **Коэффициенты LR-AGREE**, среднее по группе: клон–клон {n(co['mean']['клон–клон'])} ({co['n']['клон–клон']}), deduped–клон {n(co['mean']['deduped–клон'])} ({co['n']['deduped–клон']}), прочие {n(co['mean']['прочие'])} ({co['n']['прочие']}).")
a('  - Совпадение с клоном LR-AGREE весит меньше половины совпадения с прочими головами: голоса клонов он не считает независимыми доводами.')
sp = r['signature_descr']['pairs']
cl_ood = [v[1] for k, v in sp.items() if k.count('pythia-2.8b@') + (k.split('|')[0] == 'pythia-2.8b') + (k.split('|')[1] == 'pythia-2.8b') >= 2]
a(f"  - Совпадение pythia-2.8b-deduped с клонами весит как прочие. При этом пара pythia-2.8b и pythia-2.8b-deduped делит неверные ответы сильнее любой пары клонов: на тесте {n(sp['pythia-2.8b|pythia-2.8b-deduped'][0])} и {n(sp['pythia-2.8b|pythia-2.8b-deduped'][1])} (ID и OOD), у пар клон–клон на OOD {n(min(cl_ood))}–{n(max(cl_ood))}. Объяснение не проверялось.")
am = fa['auroc_mean']
a(f"- **AUROC вне диапазона**, среднее по головам: LR-AGREE {n(am['LR-AGREE'])}, NB-AGREE {n(am['NB-AGREE'])}, NB-IND {n(am['NB-IND'])}, FAM-AGREE {n(am['FAM-AGREE'])}, AGREE {n(am['AGREE'])}, CONF {n(am['CONF'])}.")
a(f"  - LR-AGREE выше AGREE у всех 9 голов. Выше CONF — у 7: CONF выше у {' и '.join(fa['auroc_heads']['CONF_gt_LR'])}.")
aw = r['all_wrong_ood_descr']
a(f"- **Доля задач OOD, где все головы неверны**, — {n(aw['all_wrong'])}; где все неверны и дали один и тот же ответ — 0.")
a(f"- **ПОДПИСЬ:** ранговая корреляция долей одинаковых неверных ответов ID → OOD — {n(r['signature_descr']['all'])} (все пары), {n(r['signature_descr']['without_clone_pairs'])} без пар клон–клон.")
a('')
a('## 5. Тест против пилота')
pt = fa['pilot_vs_test_rules']
a(f"- **R1:** пилот {n(pt['R1']['pilot'], 4)}, тест {n(pt['R1']['test'], 4)}. **R3:** {n(pt['R3']['pilot'], 4)} и {n(pt['R3']['test'], 4)}. **R2:** {n(pt['R2']['pilot'], 4)} и {n(pt['R2']['test'], 4)}.")
a(f"- **R4:** пилот {n(pt['R4']['pilot_all_crowds'], 4)} (по всем составам), тест {n(pt['R4']['test_fixed_crowds'], 4)} (по закреплённым).")
a(f"- ИОИ оценщиков на тесте выше пилотных на {n(min(v['diff'] for k, v in fa['pilot_vs_test_ioi'].items() if k != 'FAM-AGREE'), 3)}–{n(max(v['diff'] for v in fa['pilot_vs_test_ioi'].values()), 3)}; у FAM-AGREE — ниже на {n(-fa['pilot_vs_test_ioi']['FAM-AGREE']['diff'], 3)}.")
a(f"- Верхние 10 % выбранных: на пилоте ({pr['evaluators']['AGREE']['top10_sel']['n']} задач) LR-AGREE {n(pr['evaluators']['LR-AGREE']['top10_sel']['deception'])}, CONF {n(pr['evaluators']['CONF']['top10_sel']['deception'])}; на тесте ({fa['top10_sel_n']}) — {n(E['LR-AGREE']['top10_sel']['deception'])} и {n(E['CONF']['top10_sel']['deception'])}.")
a('')
a('## 6. Для главного вопроса (оценщик)')
a('- **Выученное согласие снижает средний ИОИ (R1), но под давлением отбора отличия от простого согласия не видно.**')
a(f"  - У LR-AGREE наименьший ИОИ по точке ({n(E['LR-AGREE']['ioi'])}). Превосходство подтверждено только над AGREE и NB-IND; против CONF ДИ {ci(r['descr_LR−CONF'])}, против FAM-AGREE {ci(r['descr_LR−FAM'])} — оба накрывают 0.")
a('  - Выигрыш ложится и на скромность, и на точность; доминирование C не установлено.')
a(f"  - В верхних 10 % выбранных ответов все пять оценщиков по согласию обманываются на {n(min(E[e]['top10_sel']['deception'] for e in E if e != 'CONF'), 2)}–{n(max(E[e]['top10_sel']['deception'] for e in E if e != 'CONF'), 2)}. Ниже всех там самообман у собственной уверенности головы: CONF {n(E['CONF']['top10_sel']['deception'])} против {n(E['LR-AGREE']['top10_sel']['deception'])} у LR-AGREE и {n(E['AGREE']['top10_sel']['deception'])} у AGREE.")
a('  - Почему верхушка согласия обманывается — объяснение не проверялось.')
a(f"- **Описательно, OCGEO-01.** Там (другая задача, 5 голов) самообман AGREE в верхних 10 % пар — 0,026, ничьи по индексу. Здесь по варианту «все пары» — {n(E['AGREE']['top10_all']['deception'])}, ничьи дробно.")
a('  - Совет 54 снял вариант «все пары» с главной меры (ERRORS № 157). Причина разницы не разделена; пересчёт OCGEO-01 по выбранным ответам — в описи.')
a('- **Что дальше** (только опись; новые линии заморожены, `docs/PROPOSALS_INVENTORY.md`):')
a('  - ОЦЕНЩИК-СМЕСЬ: отбор по уверенности головы, согласие — как вето. Правило — в новой PREREG по ID и пилоту; на этих 6297 ответах — только вторичный анализ без веса; подтверждение — на свежем наборе OOD;')
a('  - контроль на неспецифичность: LR-AGREE на перемешанных парах;')
a('  - пересчёт OCGEO-01 по выбранным ответам;')
a('  - пара pythia-2.8b и pythia-2.8b-deduped («скрытое родство») — пост-хок гипотеза, объяснение не проверялось;')
a('  - ОЦЕНЩИК-ОТКАЗ.')
a('')
a('## 7. Ограничения')
a('- Одна задача (сложение), одно семейство клонов, все головы — Pythia. OPT и GPT-Neo не прошли проверку метода.')
a('- R1 — по правилу §5 «оценщик скромнее», не «распознаёт общие ошибки». Доля C у порога 0,5, вклад точности не исключён.')
a('- R3 — преимущество над NB-IND, не специфичность к общим ошибкам. Подтверждён при мощности 0,182, эффект, вероятно, завышен; неспецифичная альтернатива (сдвиг ID → OOD) не проверена.')
a(f"- Решающая граница R1 опирается на один повтор (z₀ {n(R1['z0'], 3, True)}). Вердикт устойчив: все повторы < 0, обе половины согласны.")
a(f"- Верхние 10 % — {fa['top10_sel_n']} задач. Малые разности (LR-AGREE − AGREE) на них не различить.")
a('- FAM-AGREE знает клонов по имени. Подгонка и калибровка — на одних задачах ID (кросс-подгонка — только точка).')
a('- Сверки площадок нет: повтор пилота получил тот же T4.')
a('')
a('## 8. Вес опоры (PREREG §6; правило записано до данных)')
a(f"- R1 — подтверждено: +{n(fa['weights_bits']['R1'], 2)} бита = log₂(0,675 / 0,0025).")
a(f"- R3 — подтверждено: +{n(fa['weights_bits']['R3'], 2)} бита = log₂(0,182 / 0,0025).")
a('- R2, R4 — не решено: 0 бит.')
a('- Мощность осторожная: эффект пилота ужат вдвое, стандартная ошибка — по числу задач OOD.')
a('- Повторено (пилот и тест), не установлено. Для «установлено» нужен повтор с контролем на неспецифичность (CLAUDE.md).')
a('- C-086 и C-087 получены на одном прогоне и одних данных — одна группа опор. Как независимые опоры другого вывода их не складывать.')
sb = fa['support_bits']
a(f"- **Вес опоры: {n(sb['R1_total'], 1)} бита** (C-086: база «гипотеза_neu» {n(sb['base_hypothesis_neu'], 2, True)} и R1 {n(fa['weights_bits']['R1'], 2, True)}); C-087 — {n(sb['R3_total'], 1)} бита (R3); описательное C-088 — только база.")
a('')
a('## 9. Отклонения')
a('- Отклонений от PREREG нет. Тест на Kaggle T4 стартовал сразу после пуша, запасные площадки не понадобились.')
a('- Задача `neu-occor-pilot-p100` получила T4 вместо P100. PREREG §3 называл её только сверкой площадок; сверки не вышло (§1).')
open(os.path.join(X, 'REPORT-OCCOR-01.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\n'.join(L))
