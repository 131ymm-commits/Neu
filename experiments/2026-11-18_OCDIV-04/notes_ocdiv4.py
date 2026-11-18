#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-04: заметки после данных для REPORT-OCDIV-04.md (после совета 73 — с его правками «нужно») — разделы «Коротко» (дополнение), «Для главного вопроса», «Что дальше», «После
данных» и совет. Написаны после вывода анализа теста (каркас report_ocdiv4.py закоммичен до данных, в регистрации 5a7706fe). Текст мой; числа
подставляются из json тем же форматированием, что в report_ocdiv4.py, — в тексте нет чисел из памяти. Производные числа пишутся в
notes_derived4.json — его читает ledger.py audit. Вердиктов и чтения скрипт не меняет.
  python3 notes_ocdiv4.py
Время заданий извлечения — только поле seconds через tools/raw_status.filtered (белый список)."""
import glob
import json
import os
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import raw_status  # noqa: E402

a = sys.argv[1:]
A = json.load(open(os.path.join(ROOT, 'gha_out/ocdiv4_sum_test/analysis.json'), encoding='utf-8'))
PN = json.load(open(os.path.join(ROOT, 'gha_out/ocdiv4_sum_pilot3/pilot.json'), encoding='utf-8'))
TR = json.load(open(os.path.join(ROOT, 'gha_out/ocdiv4_sum_test/trunc.json'), encoding='utf-8'))
OUT, OUT_DER = os.path.join(X, 'report_notes.json'), os.path.join(X, 'notes_derived4.json')


def f(x, d=4):                                  # то же, что report_ocdiv4.f
    if x is None or x != x:
        return '—'
    return f'{x:+.{d}f}'.replace('-', '−').replace('.', ',')


def g(x, d=4):                                  # то же, что report_ocdiv4.g
    if x is None or x != x:
        return '—'
    return f'{x:.{d}f}'.replace('.', ',')


def iv(c, d=4):
    return f'[{f(c[0], d)}; {f(c[1], d)}]'


def tt(x, d=2):                                 # t со знаком «−», как у f
    return g(x, d).replace('-', '−')


R, RA, D = A['rules'], A['rules_alt'], A['descr']
FT, FL = A['families']['thousands'], A['families']['length']
assert A['n3c_fit'] is False and R['Р1-Л']['active'] and R['Р1-Л']['key'] == 'n0c_ood', 'тексты написаны под этот путь нуля'
assert R['Р1-Л']['verdict_rule'] == 'подтверждено' and RA['Р1-Т']['verdict_rule'] == 'подтверждено' and RA['Р1-Л']['verdict_rule'] == 'подтверждено'
assert R['Р1-Т']['verdict_rule'].startswith('в среднем этих сред') and R['Р1-Т']['mark'] == 'знак по средам разный'
assert R['Р2-Т']['verdict_rule'].startswith('в среднем этих сред: вне диапазона меньше')
assert FT['method_ok'] and FL['method_ok'] and len(FT['use']) == 8 and len(FL['use']) == 3


def short_env(n):
    return n.replace('_p3', '')


def by_env(F, key):
    return ', '.join(f"{short_env(n)} {f(F['envs'][n][key]['point'])}" for n in F['use'])


def signs(e):
    s = e['signs']
    return len(s['pos']), len(s['neg']), len(s['zero'])


secs = []
for p in sorted(glob.glob(os.path.join(ROOT, 'gha_out', 'ocdiv4_test_*', 'answers_*.json'))):
    s = raw_status.filtered(json.load(open(p, encoding='utf-8'))).get('seconds')
    if s is not None:
        secs.append(s)
kinds_top = {n: max(e['same_pairs_ood']['kinds'].items(), key=lambda kv: kv[1]) for F in (FT, FL) for n, e in F['envs'].items()}
share_m100 = {n: FT['envs'][n]['same_pairs_ood']['kinds'].get('−10^2', 0.0) for n in FT['use']}
ex = {n: e['extra_tokens'] for F in (FT, FL) for n, e in F['envs'].items() if e['extra_tokens']['n_cells']}
pa, rc = A['pairs'], A['repeat_check']
pn0 = {n: PN['families']['length']['envs'][n]['n0c_ood']['point'] for n in FL['use']}
n0l = {n: FL['envs'][n]['n0c_ood']['point'] for n in FL['use']}
t4l = {n: FL['envs'][n]['t4_ood']['point'] for n in FL['use']}
f_l = {n: FL['envs'][n]['d3c_ood']['F'] for n in FL['use']}
ceil = {n: n0l[n] / (1 - f_l[n]) for n in FL['use']}                 # совет 73, «потолок»: доля Δ0c от запаса 1 − F (пост-хок)
top_l = max(n0l, key=lambda n: n0l[n])
tr_rows = [r for r in TR['rows'] if r.get('n_extra_tokens')]
assert len(tr_rows) == 1, 'текст о приборе написан под одну строку trunc.json'
tr = tr_rows[0]
CJ = json.load(open(os.path.join(ROOT, 'docs/council/2026-11-18_OCDIV-04-report_session73.json'), encoding='utf-8'))
der = dict(source='notes_ocdiv4.py по analysis.json, pilot.json (третий разбор пилота), trunc.json, стенограмме совета 73 и полю seconds вывода заданий',
           r1l_sign_counts=signs(R['Р1-Л']), r1t_sign_counts=signs(R['Р1-Т']), alt_r1t_sign_counts=signs(RA['Р1-Т']),
           alt_r1l_sign_counts=signs(RA['Р1-Л']), r2t_sign_counts=signs(R['Р2-Т']),
           pilot_n0c_length=pn0, pilot_r2t_mu=PN['power']['Р2-Т']['mu'], n0c_length=n0l, t4_length=t4l, F_length=f_l,
           ceiling_share_length=ceil, r1l_top_env=top_l, r1l_top_share=n0l[top_l] / (3 * R['Р1-Л']['delta']),
           z_star={src: {r: e['z_star'] for r, e in A[src].items()} for src in ('rules', 'rules_alt')},
           share_minus100_min=min(share_m100.values()), share_minus100_max=max(share_m100.values()),
           kinds_top={n: [k, v] for n, (k, v) in kinds_top.items()},
           extract_seconds_max=max(secs), extract_seconds_min=min(secs), extract_minutes_max=max(secs) / 60, n_answer_files=len(secs),
           analysis_seconds=A['seconds'], analysis_minutes=A['seconds'] / 60,
           pairs_rank=round(pa['p_exact'] * pa['n_structures']), max_abs_dlogp=max(x['max_abs_dlogp'] for x in rc),
           series_confirm=A['level'], series_with_refute=2 * A['level'],
           trunc_extra_T=TR['summary']['test3 T']['n_extra_tokens'], trunc_extra_L=TR['summary']['test3 L']['n_extra_tokens'],
           trunc_row=dict(model=tr['model'], env=tr['env'], phase=tr['phase'], n_extra_tokens=tr['n_extra_tokens']),
           weight_r1l_bits=__import__('math').log2(PN['power_alt']['Р1-Л (N0c)']['power']['confirm'] / A['level']),
           council_status=CJ['status'], council_over_s=CJ['timer'].get('over_s'))
json.dump(der, open(OUT_DER, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

r1l, r1t, r2t, a1t, a1l = R['Р1-Л'], R['Р1-Т'], R['Р2-Т'], RA['Р1-Т'], RA['Р1-Л']
ILL = 'описательно, нуль N3c не прошёл положительный контроль'
short = [
    f"**Р1-Л — что утверждается** (совет 73, «нужно» 1–2): подтверждено только по части А, в среднем этих трёх сред; на новые среды не "
    f"переносится (t по средам {tt(r1l['t_envs']['t'])} < {g(r1l['t_envs']['crit'], 3)}). Среднее держится в основном на {short_env(top_l)} "
    f"({f(n0l[top_l])}); L_X999 ({f(n0l['L_X999_p3'])}) накрывает 0. Вес {g(der['weight_r1l_bits'], 2)} бита — верхняя оценка. Формулировка: ошибки "
    "голов на «длине» не независимы относительно N0c; что сверх общей трудности задач — не определено (неспецифично); совпадение значений не "
    "отделено. Чтение PREREG §5 («сосредоточены на одних задачах, или совпадают по значению, или то и другое») совет сузил после данных; вердикт "
    "это не меняет.",
    f"**Δ0c почти равно Т4 по N0** во всех трёх средах «длины» (Δ0c / Т4): "
    + '; '.join(f"{short_env(n)} {f(n0l[n])} / {f(t4l[n])}" for n in FL['use']) + ". Страты c1 к нулю почти ничего не добавляют. Объяснение не "
    "проверялось. В пилоте Δ0c: " + ', '.join(f"{short_env(n)} {f(pn0[n])}" for n in FL['use']) + ".",
    f"**Ветвь N3c ({ILL}):** на «тысячах» нижняя граница M4 > 0 и t по средам выше порога — Δ3c {f(a1t['delta'])}, M4 {iv(a1t['ci'])}, t "
    f"{tt(a1t['t_envs']['t'])} при пороге {g(a1t['t_envs']['crit'], 3)}; интервал среды больше нуля в {der['alt_r1t_sign_counts'][0]} средах, "
    f"накрывает 0 в {der['alt_r1t_sign_counts'][2]} (T_X49, T_X89), меньше нуля — нигде. На «длине» — {f(a1l['delta'])} {iv(a1l['ci'])}. Так "
    "выглядел бы Р1-Т при годном N3c; вердикта и веса нет.",
    f"**N3cu ({ILL}; страты-клетки c1 × u, M4 при 0,005):** «тысячи» {f(D['thousands d3u_ood']['delta'])} {iv(D['thousands d3u_ood']['ci'])}, "
    f"«длина» {f(D['length d3u_ood']['delta'])} {iv(D['length d3u_ood']['ci'])} — нижние границы > 0. Избыток в клетках меньше, чем в стратах "
    "c1; почему — не проверялось.",
    f"**Р1-Т по N0c (описательно, заранее неинформативен):** {f(r1t['delta'])} {iv(r1t['ci'])}, t {tt(r1t['t_envs']['t'])}; знак по средам "
    f"разный — больше нуля {der['r1t_sign_counts'][0]}, меньше {der['r1t_sign_counts'][1]}, накрывает 0 {der['r1t_sign_counts'][2]}. Урок (совет "
    "73): M4 по задачам при фиксированных средах даёт нижнюю границу > 0 и тогда, когда знаки по средам расходятся.",
    f"**Р2-Т (описательно) — находка против гипотезы о специфичности сдвига:** K вне диапазона минус K на ID — {f(r2t['delta'])} "
    f"{iv(r2t['ci'])}, t {tt(r2t['t_envs']['t'])} при пороге {g(r2t['t_envs']['crit'], 3)}. В этих восьми средах совпадение смещений при "
    f"совместной ошибке на ID сильнее, чем вне диапазона; знак тот же, что в пилоте (μ {f(der['pilot_r2t_mu'])}).",
]
main_q = [
    "**Вывода «согласие голов не служит независимым доводом» опыт не даёт** (совет 73, «нужно» 5). Правилом подтверждена только неспецифичная "
    "зависимость ошибок на трёх средах «длины» относительно N0c. Проверено по коду: F считает ничью и задачи без верного голоса "
    "(`ocdiv2.false_major`: неверный ответ набрал не меньше голосов, чем верный). Поэтому одна общая трудность задач поднимает F над F₀(N0c) и "
    "без совпадения значений; сколько дают трудность и сколько совпадение, опыт не разделил.",
    f"**Иллюстрации ({ILL}):** K (доля одинаковых смещений среди совместных ошибок пары сверх N3c) — «тысячи»: вне диапазона "
    f"{f(D['thousands k_ood']['delta'])}, на ID {f(D['thousands k_id']['delta'])}; «длина»: {f(D['length k_ood']['delta'])} и "
    f"{f(D['length k_id']['delta'])}. Δ3c на ID — {f(D['thousands d3c_id']['delta'])} {iv(D['thousands d3c_id']['ci'])} и "
    f"{f(D['length d3c_id']['delta'])} {iv(D['length d3c_id']['ci'])}. Совпавшие смещения на «тысячах» — чаще всего −10² (доля "
    f"{g(der['share_minus100_min'], 3)}–{g(der['share_minus100_max'], 3)} по средам), затем −10¹; на L_X9 — −10¹: вид «потеря переноса в разряде». "
    "Почему разные головы теряют один и тот же перенос, не проверялось.",
    "**Границы:** правило с вердиктом одно (Р1-Л, нуль N0c, три среды «длины»); главный вопрос опыта остался в описательной ветви N3c, потому "
    "что положительный контроль N3c не пройден в T_X49_p3. Семь малых открытых голов, одна подсказка (p = 3), сложение.",
]
nxt = [
    "**Реестр (совет 73, «нужно» 8):** C-107 остаётся «гипотезой», 0 бит. Р1-Л — новая запись «подтверждено» в формулировке «нужно» 2; вес в "
    "journal/support_bits.json не вносится (PREREG §10). «Установлено» — ничему.",
    "**Линия OCDIV остановлена до слова автора.** Следующий в очереди — LINUX-02. Проект нуля совпадения значений — в опись, ставится только по "
    "слову автора. По совету: главный нуль сохраняет маску ошибок и переставляет неверные значения внутри задачи и страты; второй слой сохраняет "
    "трудность и переставляет, кто ошибся; положительный контроль — вброс совпадений, закреплённый до прогона, подбор и проверка на разных "
    "половинах; мощность не меньше 0,8 на задачах подбора. Хватит ли уже собранных ответов, не проверено.",
]
notes = [
    "**Урок о запасном нуле** (совет 73, «нужно» 7; ERRORS № 207): правило «N3c не годен → N0c» переключило опыт на нуль без контроля "
    "специфичности. Такой нуль даёт «подтверждено» почти при любой общей трудности задач. Правило записано до теста, так что подгонки по данным "
    "нет; предположение «запасной нуль отвечает на тот же вопрос» не проверялось.",
    f"**Поле z_star** в analysis.json — наблюдаемое отношение Δ к ст. откл. повторов (Р1-Т {g(der['z_star']['rules']['Р1-Т'], 2)}, Р1-Л "
    f"{g(der['z_star']['rules']['Р1-Л'], 2)}), а не порог z = {g(A['z'], 3)}.",
    f"**«Потолок» (пост-хок, описательно):** доля Δ0c от запаса 1 − F по средам «длины» — "
    + ', '.join(f"{short_env(n)} {g(ceil[n], 3)} (F {g(f_l[n], 4)})" for n in FL['use']) + ". Объяснение не проверялось.",
    f"**Детерминизм:** {len(rc)} повтора на других процессорах — ответы совпали во всех 2200 задачах каждого, наибольшая |Δ logp| — "
    f"{g(der['max_abs_dlogp'], 6)}.",
    f"**Прибор:** {tr['n_extra_tokens']} ответов с лишними токенами (`trunc.json`; все — {tr['model'].split('/')[-1]} на {tr['env']}, {tr['phase']}); "
    + '; '.join(f"в толпе — {e['n_cells']} ячеек ({short_env(n)}, поле families.thousands.envs.{n}.extra_tokens.n_cells); пересчёт Δ3c с ними как "
                f"«без числа» {f(e['recount']['d3c'])} (основной счёт {f(FT['envs'][n]['d3c_ood']['point'])})" for n, e in ex.items())
    + ". Проверено по коду: критерий один (n_tok больше числа цифр + 1), но прибор анализа считает только задачи вне диапазона, а "
    "`trunc_check.py` — все задачи среды. Вне T_X19_p3 лишних токенов нет; вердикт — по основному счёту.",
    f"**Время:** задания извлечения — от {g(der['extract_seconds_min'], 1)} до {g(der['extract_seconds_max'], 1)} с (наибольшее — "
    f"{g(der['extract_minutes_max'], 1)} мин); анализ — {g(der['analysis_seconds'], 1)} с ({g(der['analysis_minutes'], 1)} мин) при пределе 180 мин. "
    "Все 80 заданий и анализ прошли с первого раза; отступлений от PREREG в счёте нет (правка текста отчёта по совету 73 — DEVIATIONS.md).",
    f"**Пары производителей:** контраст {f(pa['observed'])}, точное p = {g(pa['p_exact'])} ({der['pairs_rank']} из {pa['n_structures']} структур) — "
    "от нуля не отличён.",
    f"**Общий ложный уровень серии:** правило с вердиктом одно — ложное «подтверждено» не больше {g(der['series_confirm'], 4)}, с ложным "
    f"«опровергнуто» — не больше {g(der['series_with_refute'], 3)}. Номинально: перенос M4 на {g(A['level'], 4)} для среднего сред не проверен.",
    "**Сверка чисел:** `check_report4.py` сравнивает числа правил, ветви, сред, описательного и ожиданий в отчёте со значениями по путям в "
    "analysis.json; `ledger.py audit` — числа отчёта против файлов данных.",
]
votes = CJ['votes']
n_for = sum(v['vote'] == 'за' for v in votes)
assert CJ['status'] == 'принято единогласно' and n_for == len(votes) == 4 and CJ['timer'].get('over_s') == 0
council = dict(title='Совет 73 — оценка отчёта (18.11.2026)', items=[
    f"**{CJ['status'][0].upper() + CJ['status'][1:]}: {n_for} из {len(votes)} «за» после правок «нужно»;** перебора времени нет. Стенограмма — "
    "`docs/council/2026-11-18_OCDIV-04-report_session73.md`.",
    "**Правки «нужно» 1–9 внесены:** оговорка «в среднем этих трёх сред» у Р1-Л; формулировка Р1-Л (неспецифично, совпадение не отделено) и "
    "строка Δ0c ≈ Т4; слова о границе M4 вместо «подтверждено» и «опровергнуто» у описательных строк; пояснение поля z_star; «Для главного "
    "вопроса» без опоры на N3c, N3cu и Р1-Л; прибор — 9 ответов против 8 ячеек, путь поля; урок о запасном нуле (ERRORS № 207); реестр; E4 — "
    "как сбывшееся, без пересмотра.",
    "**Несогласия:** насколько слаба формулировка Р1-Л — взята формулировка скептика (без слов «совпадают по значению»), формалист её принял; "
    "место N3cu — иллюстрация с пометкой (спора по существу нет); что такое Δ0c, кроме трудности, — открыто; цена будущего нуля не сверена.",
    "**Проверено после совета:** определение F (ничья считается ложным большинством, поэтому трудность сама поднимает F) и причина «9 против 8» — "
    "по коду; доля Δ0c от 1 − F — выше, пост-хок.",
])
json.dump(dict(short=short, main_q=main_q, next=nxt, notes=notes, council=council), open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('записано', OUT, OUT_DER)
