#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка REPORT-OCMIX-01.md: текст — мой, числа — из run/analysis.json, run/facts_ocmix.json, analysis_pilot.json, power.json
тем же форматированием, каким их сверяет ledger.py audit. python3 report_ocmix.py <папка опыта>"""
import json
import os
import sys

X = sys.argv[1]
J = lambda p: json.load(open(os.path.join(X, p), encoding='utf-8'))  # noqa: E731
r, fa, p, pw = J('run/analysis.json'), J('run/facts_ocmix.json'), J('analysis_pilot.json'), J('power.json')
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


R1, R2, R3 = r['R1'], r['R2'], r['R3']
D = lambda k: r[f'descr_{k}']  # noqa: E731
top, sb, mde = fa['top10_sel_deception'], fa['support_bits'], fa['mde_power08']
NAMES = {'AGREE': 'AGREE (согласие голов)', 'LR-AGREE': 'LR-AGREE (выученное согласие)', 'CONF': 'CONF (уверенность головы)',
         'VETO': 'VETO (уверенность, согласие — вето)', 'MIX-LR': 'MIX-LR (регрессия на согласии и уверенности)'}
L = []
a = L.append
a('# OCMIX-01 «ОЦЕНЩИК-СМЕСЬ» — отчёт (15.11.2026)')
a('')
a('Главный вопрос Neu — оценщик, который не обманывается под давлением отбора. OCMIX-01 спрашивал: если выбирать ответ по уверенности головы, а согласие других голов брать только как вето, совместится ли честность уверенности на верхушке отбора с выигрышем согласия в среднем? Сдвиг свежий: a ∈ [200, 299], ID — сумма < 300, OOD — сумма ≥ 300.')
a('- **Предрегистрация — коммит 4babbdbf** (`PREREG-OCMIX-01.md`). Первый коммит файла 088780b2 — черновик для совета 56.')
a(f"- **Прогон** — Kaggle, Tesla T4, извлечение 2022,5 с; 9 голов Pythia (те же, что в OCCOR-01); {fa['n_test']} задач теста: {r['n_id']} ID и {r['n_ood']} OOD.")
a(f"  - Сырой вывод закоммичен до анализа (d3a45c91), хеши сверены. Анализ — 346 с, {r['B']} повторов.")
a('- **Числа** — из `run/analysis.json`; производные — из `run/facts_ocmix.json` (`facts_ocmix.py`).')
a('')
a('## Итог')
a(f"**Вердикт кода — «{r['verdict']}».** Проверки метода пройдены. По PREREG §5 «не решено» у R1 и R2 читается как **«не проверено (мощность < 0,05)»**: это не довод ни за вето, ни против него.")
a(f"- **R3 — подтверждено: выученное согласие лучше простого и на свежем сдвиге.** ИОИ LR-AGREE {n(E['LR-AGREE']['ioi'])} против {n(E['AGREE']['ioi'])} у AGREE: Δ {n(R3['delta'], 4)}, ДИ BC 99,5 % {ci(R3)}.")
a(f"  - Все {r['B']} повторов < 0, обе половины повторов дают «подтверждено». Это второй независимый тест C-086 (первый — OCCOR-01).")
a(f"- **На этом сдвиге верхушка отбора честна у всех пяти оценщиков** (описательно, вес 0). Самообман в верхних 10 % выбранных ответов ({fa['top10_sel_n']} задача) — {n(fa['top10_sel_range']['min'])}–{n(fa['top10_sel_range']['max'])}.")
a(f"  - В OCCOR-01 у AGREE там было {n(fa['occor_top10_sel_deception']['AGREE'])}, здесь — {n(top['AGREE'])}. Явление C-088 на свежем сдвиге не повторилось; чем объясняется разница — не проверялось.")
a(f"- **Вето почти не срабатывало.** Выбранный ответ VETO поддержан другой головой в {n(E['VETO']['selected_supported'], 4)} задач.")
a(f"  - Если считать поддержку только от головы другой линии (другого размера), — в {n(r['support_other_lineage_descr']['VETO'])} задач (у CONF — {n(r['support_other_lineage_descr']['CONF'])}). В остальных задачах поддержку давали только родственные головы: свои чекпойнты или своя пара с deduped.")
a(f"- **R1 и R2 — не проверено.** R1 (верхушка VETO − LR-AGREE): {n(R1['delta'], 4)}, ДИ {ci(R1)}. R2 (ИОИ VETO − CONF): {n(R2['delta'], 4)}, ДИ {ci(R2)}. Мощность при эффекте пилота, ужатом вдвое, — 0,011 и 0,003.")
a(f"- **MIX-LR** (описательно): ИОИ {n(E['MIX-LR']['ioi'])} — около LR-AGREE ({n(E['LR-AGREE']['ioi'])}) и ниже VETO на {n(-D('MIX−VETO')['delta'])} (ДИ 99 % {ci(D('MIX−VETO'))}).")
a('')
a('| оценщик | T | C | незнание | самообман | ИОИ | верхние 10 % выбранных: точность / заявка / самообман |')
a('|---|---|---|---|---|---|---|')
for e in ('LR-AGREE', 'MIX-LR', 'AGREE', 'VETO', 'CONF'):
    v = E[e]; s = v['top10_sel']
    a(f"| {NAMES[e]} | {n(v['T'])} | {n(v['C'])} | {n(v['ignorance'])} | {n(v['deception'])} | {n(v['ioi'])} | {n(s['accuracy'])} / {n(s['claim'])} / {n(s['deception'])} |")
a('')
a('## 1. Прогон')
a('- **Точность голов (ID / OOD):**')
for k, v in r['accuracy'].items():
    a(f"  - {k} — {n(v['id'])} / {n(v['ood'])};")
mc = min(min(v['id_correct'], v['id_wrong'], v['ood_correct'], v['ood_wrong']) for v in r['method']['counts'].values())
a(f"- Все девять голов на видеокарте. У каждой на ID и на OOD не меньше {mc} верных и {mc} неверных ответов (порог 20). Ответов без числа и неконечных logp нет.")
a(f"- Ничьих при выборе головы — {n(min(v['tie_frac'] for v in E.values()), 4)}–{n(max(v['tie_frac'] for v in E.values()), 4)}.")
a('')
a('## 2. Вердикты по PREREG (§5)')
for k, lab in (('R1', 'R1 (верхушка VETO − LR-AGREE) — не решено, по §5 «не проверено»'), ('R2', 'R2 (ИОИ VETO − CONF) — не решено, по §5 «не проверено»'),
               ('R3', 'R3 (ИОИ LR-AGREE − AGREE) — подтверждено')):
    e = r[k]; t = e['tails']
    a(f"- **{lab}.** Δ {n(e['delta'], 4)}, ДИ BC {ci(e)}, процентильный {perc(e)}; z₀ {n(e['z0'], 3, True)}.")
    a(f"  - Хвосты: за нижней границей {t['n_below_lo']} повторов, за верхней {t['n_above_hi']}; обе половины — «{t['verdict_halves'][0]}».")
a(f"- У R1 z₀ {n(R1['z0'], 3, True)}: верхняя граница BC опирается на один повтор (оценка Монте-Карло), но вердикт «не решено» при этом не меняется — половины согласны.")
a(f"- **Защита LR:** повторов с одним классом в выборке ID — {r['lr_one_class']['reps']}.")
a('- Ложное «подтверждено» по серии из трёх правил — не выше 0,0075.')
a('')
a('## 3. Ожидания (PREREG §7)')
a('| № | ожидание | вероятность | исход |')
a('|---|---|---|---|')
ex = [('E1', 'R1 подтверждено', '0,01', 'нет'), ('E2', 'R2 подтверждено', '0,002', 'нет'), ('E3', 'R3 подтверждено', '0,35', 'да'),
      ('E4', 'проверки метода пройдены', '0,95', 'да'), ('E5', f"самообман верхушки AGREE меньше 0,15 ({n(top['AGREE'])})", '0,85', 'да'),
      ('E6', f"выбранный ответ VETO поддержан не меньше чем в 95 % задач ({n(E['VETO']['selected_supported'], 4)})", '0,90', 'да'),
      ('E7', f"точечно ИОИ MIX-LR меньше, чем у VETO ({n(E['MIX-LR']['ioi'])} против {n(E['VETO']['ioi'])})", '0,90', 'да')]
for row in ex:
    a('| ' + ' | '.join(row) + ' |')
a('- E3 — «да» при мощности 0,363. E5 и E7 после пилота были почти наверняка «да» (совет 56).')
a('')
a('## 4. Описательно (вес 0, без вердикта; ДИ BC 99 %)')
a(f"- **Разложение R2:** ΔT {n(D('R2_dT')['delta'], 4, True)} {ci(D('R2_dT'))}, ΔC {n(D('R2_dC')['delta'], 4, True)} {ci(D('R2_dC'))}. VETO точнее CONF, но и заявляет больше; по ИОИ разница внутри ДИ.")
a(f"- **Верхушка:** VETO − CONF {n(D('VETOtop−CONFtop')['delta'], 4, True)} {ci(D('VETOtop−CONFtop'))}; MIX-LR − VETO {n(D('MIXtop−VETOtop')['delta'], 4)} {ci(D('MIXtop−VETOtop'))}; MIX-LR − LR-AGREE {n(D('MIXtop−LRtop')['delta'], 4)} {ci(D('MIXtop−LRtop'))}.")
a(f"  - По всем парам «голова × задача»: AGREE {n(E['AGREE']['top10_all']['deception'])}, LR-AGREE {n(E['LR-AGREE']['top10_all']['deception'])}, CONF {n(E['CONF']['top10_all']['deception'])}, VETO {n(E['VETO']['top10_all']['deception'])}, MIX-LR {n(E['MIX-LR']['top10_all']['deception'])}.")
a(f"- **ИОИ:** VETO − LR-AGREE {n(D('VETO−LR')['delta'], 4, True)} {ci(D('VETO−LR'))}; VETO − AGREE {n(D('VETO−AGREE')['delta'], 4, True)} {ci(D('VETO−AGREE'))}.")
cf = r['crossfit_descr']
a(f"- **Кросс-подгонка** (5 частей ID, только точка): R1 {n(cf['rules']['R1'], 4)}, R2 {n(cf['rules']['R2'], 4)}, R3 {n(cf['rules']['R3'], 4)}; верхушка LR-AGREE {n(cf['evaluators']['LR-AGREE']['top10_sel']['deception'])}, MIX-LR {n(cf['evaluators']['MIX-LR']['top10_sel']['deception'])}.")
am = fa['auroc_mean']
a(f"- **AUROC вне диапазона**, среднее по головам: MIX-LR {n(am['MIX-LR'])}, LR-AGREE {n(am['LR-AGREE'])}, AGREE {n(am['AGREE'])}, VETO {n(am['VETO'])}, CONF {n(am['CONF'])}.")
a(f"- **Неподдержанные ответы на ID** — всего {fa['unsupported_id_total']} по девяти головам; больше всего у слабых голов (1.4b и 1.4b-deduped).")
a('')
a('## 5. Тест против пилота')
pt = fa['pilot_vs_test_rules']
a(f"- **R3:** пилот {n(pt['R3']['pilot'], 4)}, тест {n(pt['R3']['test'], 4)}. **R1:** {n(pt['R1']['pilot'], 4)} и {n(pt['R1']['test'], 4)}. **R2:** {n(pt['R2']['pilot'], 4)} и {n(pt['R2']['test'], 4)}.")
a(f"- Верхушка на пилоте ({p['full']['AGREE']['top10_sel']['n']} задач) — 0,041–0,080; на тесте ({fa['top10_sel_n']}) — {n(fa['top10_sel_range']['min'])}–{n(fa['top10_sel_range']['max'])}.")
a('')
a('## 6. Для главного вопроса (оценщик)')
a('- **Выученное согласие лучше простого в среднем — это повторилось на свежем сдвиге (R3).** Вывод C-086 теперь опирается на два независимых теста.')
a(f"- **Самообман верхушки согласия — не постоянное свойство согласия.** В OCCOR-01 у оценщиков по согласию он был около {n(fa['occor_top10_sel_deception']['AGREE'], 2)}, на этом сдвиге — {n(fa['top10_sel_range']['min'], 2)}–{n(fa['top10_sel_range']['max'], 2)} у всех. Что его включает — объяснение не проверялось.")
a('- **Вето на этом сдвиге проверить не удалось:** исправлять было нечего, а примерно в трети задач выбранный ответ поддерживали только родственные головы.')
a('- **Что дальше** (только опись; линии заморожены): ВЕТО-ЛИНИЯ (поддержка только от другой линии) и проверка вето на сдвиге, где у согласия есть самообман на верхушке — `docs/PROPOSALS_INVENTORY.md`.')
a('')
a('## 7. Ограничения')
a('- Одна задача (сложение), один новый сдвиг, те же девять голов Pythia, что в OCCOR-01: «свежий сдвиг» — не свежие головы.')
a('- R1 и R2 — «не проверено»: мощность 0,011 и 0,003. О вето они ничего не говорят.')
a('- R3 повторяет C-086 без контроля на неспецифичность: NB-IND в этом опыте не считался.')
a('- LR-AGREE и MIX-LR подгоняются и калибруются на одних задачах ID; кросс-подгонка — только точка.')
a('')
a('## 8. Вес опоры (PREREG §6; правило записано до данных)')
a(f"- R3 — подтверждено: +{n(sb['R3_weight'], 2)} бита = log₂(0,363 / 0,0025).")
a('- R1, R2 — «не проверено»: 0 бит, в реестр не идут.')
a(f"- C-086 получает вторую независимую группу опор: итог {n(sb['C086_total_two_groups'], 1)} бита = база «гипотеза_neu» {n(sb['base_hypothesis_neu'], 2, True)} + OCCOR-01 {n(sb['occor_R1_weight'], 2, True)} + OCMIX-01 {n(sb['R3_weight'], 2, True)}.")
a('- Повторено дважды; для «установлено» нужен повтор с контролем на неспецифичность (CLAUDE.md): в OCMIX-01 контроля нет.')
a(f"- **Вес опоры: {n(sb['C086_total_two_groups'], 1)} бита** (C-086, `python3 tools/support_bits.py`).")
a('')
a('## 9. Отклонения')
a('- Отклонений от PREREG нет. Тест на Kaggle T4 стартовал сразу после пуша.')
a('- Код после прогона — сборка отчёта (`facts_ocmix.py`, `report_ocmix.py`), вердиктов не меняет (`DEVIATIONS.md`).')
open(os.path.join(X, 'REPORT-OCMIX-01.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\n'.join(L))
