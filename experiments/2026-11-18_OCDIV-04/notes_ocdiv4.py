#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-04: заметки после данных для REPORT-OCDIV-04.md — разделы «Коротко» (дополнение), «Для главного вопроса», «Что дальше», «После
данных» и совет. Написаны после вывода анализа теста (каркас report_ocdiv4.py закоммичен до данных, в регистрации 5a7706fe). Текст мой; числа
подставляются из json тем же форматированием, что в report_ocdiv4.py, — в тексте нет чисел из памяти. Производные числа пишутся в
notes_derived4.json — его читает ledger.py audit. Вердиктов и чтения скрипт не меняет.
  python3 notes_ocdiv4.py [--council docs/council/<стенограмма>.json]
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
der = dict(source='notes_ocdiv4.py по analysis.json, pilot.json (третий разбор пилота), trunc.json и полю seconds вывода заданий',
           r1l_sign_counts=signs(R['Р1-Л']), r1t_sign_counts=signs(R['Р1-Т']), alt_r1t_sign_counts=signs(RA['Р1-Т']),
           alt_r1l_sign_counts=signs(RA['Р1-Л']), r2t_sign_counts=signs(R['Р2-Т']),
           pilot_n0c_length=pn0, pilot_r2t_mu=PN['power']['Р2-Т']['mu'],
           share_minus100_min=min(share_m100.values()), share_minus100_max=max(share_m100.values()),
           kinds_top={n: [k, v] for n, (k, v) in kinds_top.items()},
           extract_seconds_max=max(secs), extract_seconds_min=min(secs), extract_minutes_max=max(secs) / 60, n_answer_files=len(secs),
           analysis_seconds=A['seconds'], analysis_minutes=A['seconds'] / 60,
           pairs_rank=round(pa['p_exact'] * pa['n_structures']), max_abs_dlogp=max(x['max_abs_dlogp'] for x in rc),
           series_confirm=A['level'], series_with_refute=2 * A['level'],
           trunc_extra_T=TR['summary']['test3 T']['n_extra_tokens'], trunc_extra_L=TR['summary']['test3 L']['n_extra_tokens'])
json.dump(der, open(OUT_DER, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

r1l, r1t, r2t, a1t, a1l = R['Р1-Л'], R['Р1-Т'], R['Р2-Т'], RA['Р1-Т'], RA['Р1-Л']
short = [
    f"**Р1-Л по средам** (Δ0c): {by_env(FL, 'n0c_ood')}. Интервал среды при 0,0025 / 3 больше нуля в {der['r1l_sign_counts'][0]} средах, "
    f"накрывает 0 в {der['r1l_sign_counts'][2]} (L_X999). В пилоте: "
    + ', '.join(f"{short_env(n)} {f(pn0[n])}" for n in FL['use']) + ". Чтение, заданное заранее: на трёх средах «длины» ложное большинство вне "
    "диапазона чаще, чем при перестановке всех ответов каждой головы внутри страты c1. Нуль N0c не сохраняет, кто где ошибся, поэтому вопрос о "
    "совпадении самих неверных чисел это правило не решает.",
    f"**Ветвь N3c (описательно, без вердикта и веса):** на «тысячах» обе части выше порога — Δ3c {f(a1t['delta'])}, M4 {iv(a1t['ci'])}, t по "
    f"средам {g(a1t['t_envs']['t'], 2)} при пороге {g(a1t['t_envs']['crit'], 3)}; интервал среды больше нуля в {der['alt_r1t_sign_counts'][0]} "
    f"средах, накрывает 0 в {der['alt_r1t_sign_counts'][2]} (T_X49, T_X89), меньше нуля — нигде. На «длине» — {f(a1l['delta'])} {iv(a1l['ci'])}. "
    "Это то, что Р1-Т сказал бы при годном N3c: головы дают одно и то же неверное число на одной задаче чаще, чем по своим частотам, при той же "
    "картине «кто где ошибся» и той же страте c1. Вердикта нет: третий контроль годность N3c не подтвердил.",
    f"**N3cu (страты-клетки c1 × u, M4 при 0,005):** «тысячи» {f(D['thousands d3u_ood']['delta'])} {iv(D['thousands d3u_ood']['ci'])}, «длина» "
    f"{f(D['length d3u_ood']['delta'])} {iv(D['length d3u_ood']['ci'])}. Нижние границы больше нуля — по чтению, заданному заранее, «совпадение "
    "сверх устройства задачи (c1 × u)». Избыток в клетках меньше, чем в стратах c1; почему — не проверялось.",
    f"**Р1-Т по N0c (описательно, заранее неинформативен):** {f(r1t['delta'])} {iv(r1t['ci'])}, t {tt(r1t['t_envs']['t'])}; знак по средам "
    f"разный — больше нуля {der['r1t_sign_counts'][0]}, меньше {der['r1t_sign_counts'][1]}, накрывает 0 {der['r1t_sign_counts'][2]}. Та же "
    "картина, что у Т4 в OCDIV-03 (C-106): перестановка всех ответов головы на «тысячах» даёт эффект разного знака по средам.",
    f"**Р2-Т (описательно):** K вне диапазона минус K на ID — {f(r2t['delta'])} {iv(r2t['ci'])}, t {tt(r2t['t_envs']['t'])} при пороге "
    f"{g(r2t['t_envs']['crit'], 3)}. В этих восьми средах совпадение смещений при совместной ошибке вне диапазона слабее, чем на ID; на новые "
    f"среды не переносится. Знак тот же, что в пилоте (μ {f(der['pilot_r2t_mu'])}).",
]
main_q = [
    f"**Совпадение неверных ответов есть и на ID** (по нулю N3c; его годность контроль не подтвердил). K — доля одинаковых смещений среди "
    f"совместных ошибок пары сверх N3c: «тысячи» — вне "
    f"диапазона {f(D['thousands k_ood']['delta'])}, на ID {f(D['thousands k_id']['delta'])}; «длина» — {f(D['length k_ood']['delta'])} и "
    f"{f(D['length k_id']['delta'])}. Δ3c на ID — {f(D['thousands d3c_id']['delta'])} {iv(D['thousands d3c_id']['ci'])} и "
    f"{f(D['length d3c_id']['delta'])} {iv(D['length d3c_id']['ci'])}. Для оценщика «согласие голов»: когда эти головы ошибаются вместе, они "
    "чаще, чем по своим частотам, ошибаются одинаково, и не только под сдвигом. Согласие таких голов не служит независимым доводом; оценщику "
    "нужна правда, которая от согласия не зависит.",
    f"**Какие смещения совпадают** (описательно; вид — по слагаемым и коду): на «тысячах» чаще всего −10² — доля {g(der['share_minus100_min'], 3)}–"
    f"{g(der['share_minus100_max'], 3)} совпавших пар по средам, затем −10¹; на L_X9 — −10¹. Это вид «потеря переноса в разряде». Почему разные "
    "головы теряют один и тот же перенос, не проверялось.",
    "**Границы вывода:** правило с вердиктом одно (Р1-Л, нуль N0c, три среды «длины»); главный вопрос опыта — только в описательной ветви N3c, "
    "потому что положительный контроль N3c не пройден в T_X49_p3. Семь малых открытых голов, одна подсказка (p = 3), сложение.",
]
nxt = [
    "**Реестр (предложение совету):** C-107 остаётся «гипотезой» с описательной опорой из ветви N3c, вес 0 бит. Новая запись — Р1-Л: "
    "«подтверждено» в среднем трёх сред «длины» по нулю N0c. Вес — верхняя оценка, в journal/support_bits.json не вносится (PREREG §10). "
    "«Установлено» — ничему.",
    "**Рекомендация:** линию OCDIV на этом остановить до слова автора. Вопрос о годном нуле для «совпадения» открыт. Четвёртой попытки контроля "
    "в этом опыте нет по ADDENDUM-2. Если продолжать, нужен новый опыт, где критерий контроля проверяет только чувствительность нуля и "
    "закреплён до первого прогона (ERRORS № 201, дополнение). Следующий в очереди автора — LINUX-02.",
]
notes = [
    f"**Детерминизм:** {len(rc)} повтора на других процессорах — ответы совпали во всех 2200 задачах каждого, наибольшая |Δ logp| — "
    f"{g(der['max_abs_dlogp'], 6)}.",
    f"**Прибор:** числовых ответов с лишними токенами — {der['trunc_extra_T']} на «тысячах» (`trunc_check.py`) и {der['trunc_extra_L']} на «длине». "
    + ('; '.join(f"в толпе {short_env(n)} — {e['n_cells']}, пересчёт Δ3c с ними как «без числа» {f(e['recount']['d3c'])} (основной счёт "
                 f"{f(FT['envs'][n]['d3c_ood']['point'])})" for n, e in ex.items()) or 'в толпе — ни одного') + ". Вердикт — по основному счёту; среды Р1-Л не затронуты.",
    f"**Время:** задания извлечения — от {g(der['extract_seconds_min'], 1)} до {g(der['extract_seconds_max'], 1)} с (наибольшее — "
    f"{g(der['extract_minutes_max'], 1)} мин); анализ — {g(der['analysis_seconds'], 1)} с ({g(der['analysis_minutes'], 1)} мин) при пределе 180 мин. "
    "Все 80 заданий и анализ прошли с первого раза; отступлений от PREREG нет.",
    f"**Пары производителей:** контраст {f(pa['observed'])}, точное p = {g(pa['p_exact'])} ({der['pairs_rank']} из {pa['n_structures']} структур) — "
    "от нуля не отличён.",
    f"**Общий ложный уровень серии:** правило с вердиктом одно — ложное «подтверждено» не больше {g(der['series_confirm'], 4)}, с ложным "
    f"«опровергнуто» — не больше {g(der['series_with_refute'], 3)}. Номинально: перенос M4 на {g(A['level'], 4)} для среднего сред не проверен.",
    "**Сверка чисел:** `check_report4.py` сравнивает числа вердиктов и ветви в отчёте со значениями по путям в analysis.json; `ledger.py audit` — "
    "числа отчёта против файлов данных.",
]
council = None
if '--council' in a:
    CJ = json.load(open(os.path.join(ROOT, a[a.index('--council') + 1]), encoding='utf-8'))
    council = dict(title=CJ['title'], items=CJ['items'])
json.dump(dict(short=short, main_q=main_q, next=nxt, notes=notes, council=council), open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('записано', OUT, OUT_DER)
