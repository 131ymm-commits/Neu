#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-02: тексты разделов «Коротко», «Для главного вопроса» и «Что дальше» отчёта. Написаны после данных теста (каркас отчёта
report_ocdiv2.py закоммичен до них: cbf9a824, 9568fde4). Текст мой; числа подставляются из json счёта тем же форматированием, что
в report_ocdiv2.py, — чтобы в тексте не было чисел из памяти. Производные числа (знаки по средам, невырожденные среды по тесту)
считаются здесь и пишутся в notes_derived.json — его читает ledger.py audit. Скрипт вердиктов не меняет.
  python3 notes_ocdiv2.py [ANALYSIS.json]
По умолчанию: gha_out/ocdiv2_sum_test/analysis.json; пишет report_notes.json и notes_derived.json рядом со скриптом."""
import json
import os
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
a = sys.argv[1:]
an = json.load(open(os.path.join(ROOT, a[0] if a else 'gha_out/ocdiv2_sum_test/analysis.json'), encoding='utf-8'))
DER = json.load(open(os.path.join(X, 'report_derived.json'), encoding='utf-8'))
PIL2 = json.load(open(os.path.join(ROOT, 'gha_out/ocdiv2_sum_pilot2/pilot.json'), encoding='utf-8'))   # разбор 1 пилота 2 (0920425a)
OUT, OUT_DER = os.path.join(X, 'report_notes.json'), os.path.join(X, 'notes_derived.json')


def n(x, d=4, sign=True):                     # то же, что report_ocdiv2.n
    if x is None or x != x:
        return '—'
    s = f'{abs(x):.{d}f}'.replace('.', ',')
    if x < 0 and float(s.replace(',', '.')) != 0:
        return '−' + s
    return ('+' if sign and x > 0 and float(s.replace(',', '.')) != 0 else '') + s


def iv(ci, d=4):
    return f'[{n(ci[0], d)}; {n(ci[1], d)}]'


V = an['verdicts']
assert V['T4'] == 'подтверждено' and an['method']['ok'] and not an['crowd_dropped'], 'тексты написаны под этот исход'
assert an['T1']['check_result'] == 'подтверждено' and an['T3']['check_result'] == 'подтверждено' and an['T2']['verdict_rule_descr'] == 'не решено'
E = an['envs']
t4 = an['T4']
pt = {k: E[k]['T4']['point'] for k in E}
hm = {k: E[k]['homoplasy'] for k in E}
pm = an['parts_mean']
nd_test = sorted([k for k in E if E[k]['oracle_ood'] >= an['nondeg']['oracle_threshold']], key=len)
der = dict(source='notes_ocdiv2.py по analysis.json',
           t4_point_by_env=pt, t4_positive_beyond_construction=[k for k in pt if pt[k] > 1e-4],
           t4_zero_by_construction=[k for k in E if E[k]['T4']['F'] == 1.0],
           homoplasy_diff_by_env={k: hm[k]['diff'] for k in E}, homoplasy_diff_positive=int(sum(hm[k]['diff'] > 0 for k in E)),
           nondeg_by_test=nd_test, n_nondeg_by_test=len(nd_test),
           t4_share_from_x9=pt['L_X9_p3'] / len(pt) / t4['delta'])
json.dump(der, open(OUT_DER, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
x9, x99, x999, x9999 = (E[k] for k in ('L_X9_p3', 'L_X99_p3', 'L_X999_p3', 'L_X9999_p3'))
rc = (an.get('repeat_check') or [{}])[0]
short = [
    f"**Сдвиг получился трудным.** Средний по головам разрыв точности ID − OOD — {n(DER['drop_mean'])}. Оракул вне диапазона (верна хоть одна "
    f"голова) падает с {n(x9['oracle_ood'], 4, False)} при X = 9 до {n(E['L_X99999_p3']['oracle_ood'], 4, False)} при X = 99999.",
    f"**Т4 подтверждено:** F − F₀ = {n(t4['delta'])}, M4 при 0,0025 — {iv(t4['ci'])}, z\\* = {n(t4['z_star'], 1, False)}; предохранитель «без одной "
    "среды» держится. Это единственное правило опыта с вердиктом.",
    f"**Но эффект — из двух сред.** L_X9_p3: {n(pt['L_X9_p3'])}; L_X99_p3: {n(pt['L_X99_p3'])}; L_X999_p3: {n(pt['L_X999_p3'])}. В L_X9999_p3 и "
    f"L_X99999_p3 F = 1 и Т4 — ноль по построению: верных голосов вне диапазона там почти нет (в L_X9999_p3 F − F₀ = {n(pt['L_X9999_p3'], 7)}). "
    f"Счёт знаков в таблице («больше нуля — 3») включает этот ноль. Без L_X9_p3 среднее — {n(t4['leave_one_range_out']['mean_without']['9'])}; "
    f"доля L_X9_p3 в среднем пяти сред — {n(der['t4_share_from_x9'], 3, False)}.",
    f"**Число переносов совпадение ошибок не объясняет:** с перестановками внутри страт по числу переносов Т4 = "
    f"{n(an['descr_T4 (другой нуль)']['delta'])}, M4 при 0,005 — {iv(an['descr_T4 (другой нуль)']['ci'])} (описательно). Других причин я не проверял.",
    f"**Заявка не видит большей части разрыва:** r = {n(an['T3']['delta'])}, M4 при 0,0025 — {iv(an['T3']['ci'])}; по невырожденным средам "
    f"{n(an['descr_T3 невырожденные среды']['delta'])}, по вырожденным {n(an['descr_T3 вырожденные среды']['delta'])}. C − T вне диапазона у POST-CV — "
    f"{n(an['T1']['delta'])}. Т1 и Т3 — проверки построения: их исход ожидаем, сведения дают величины.",
    f"**Согласие обманывается там, где ошибки совпадают** (гомоплазия, описательно). В L_X9_p3 на задачах, где не меньше 3 голов дали один и тот же "
    f"неверный ответ, AGREE заявляет {n(x9['homoplasy']['agree_claim'], 4, False)}, а доля верных — {n(x9['homoplasy']['agree_T'], 4, False)}. На остальных "
    f"задачах вне диапазона — {n(x9['homoplasy']['agree_claim_rest'], 4, False)} и {n(x9['homoplasy']['agree_T_rest'], 4, False)}. В L_X99_p3 — "
    f"{n(x99['homoplasy']['agree_claim'], 4, False)} и {n(x99['homoplasy']['agree_T'], 4, False)} против {n(x99['homoplasy']['agree_claim_rest'], 4, False)} и "
    f"{n(x99['homoplasy']['agree_T_rest'], 4, False)}. Что заявка AGREE на таких задачах выше — следует из построения AGREE; сведения даёт доля верных.",
    f"**Т2 не решено:** ИОИ(AGREE) − ИОИ(POST-CV) = {n(an['T2']['delta'])}, M4 при 0,0025 — {iv(an['T2']['ci'])}. Ожидание E5 не сбылось.",
    f"**Переносы на ID (описательно, M4 при 0,005):** wc CONF {n(an['descr_wc CONF']['delta'])} {iv(an['descr_wc CONF']['ci'])} — отбор завышает "
    f"заявку (C-090); wc POST {n(an['descr_wc POST']['delta'])} {iv(an['descr_wc POST']['ci'])} — в полосе ±0,02 (C-100); отрицательный контроль "
    f"wc FIXED {n(an['descr_wc FIXED']['delta'])} {iv(an['descr_wc FIXED']['ci'])}.",
    f"**Повтор на другом раннере:** ответы совпали во всех {rc.get('n')} задачах (доля {n(rc.get('answers_equal'), 4, False)}), наибольшее |Δ logp| — "
    f"{n(rc.get('max_abs_dlogp'), 6, False)}; процессоры {rc.get('cpu_main')} и {rc.get('cpu_rep')}. Одно задание; для остальных детерминизм не проверялся.",
    f"**Оракул теста разделил среды не так, как пилот 2:** L_X999_p3 — {n(x999['oracle_ood'], 4, False)} при пороге "
    f"{n(an['nondeg']['oracle_threshold'], 1, False)} (в пилоте 2 — ниже порога). По PREREG §3 это записано, вердикт не меняется; описательные строки "
    "«невырожденные среды» идут по списку пилота.",
]
main_q = [
    f"**На трудном сдвиге обманываются все оценщики толпы.** Самообман вне диапазона — от {n(pm['dec FIXED'], 4, False)} у одной закреплённой головы "
    f"(FIXED) до {n(pm['dec CONF'], 4, False)} у выбора по уверенности (CONF). Незнание — наоборот: {n(pm['ign FIXED'], 4, False)} и "
    f"{n(pm['ign CONF'], 4, False)}. По ИОИ CONF хуже всех ({n(pm['ioi CONF'], 4, False)}), FIXED лучше всех ({n(pm['ioi FIXED'], 4, False)}). "
    "У выбора по уверенности незнание меньше, а самообман больше, чем у одной закреплённой головы, и в сумме ИОИ хуже. Описательно: у разности "
    "CONF − FIXED интервала нет; причина не проверялась.",
    f"**Калибровка на ID не переносится за диапазон.** На ID вторая калибровка снимает завышение (wc POST в полосе), а вне диапазона "
    f"C − T у POST-CV — {n(an['T1']['delta'])}. В заявке остаётся незамеченной доля r = {n(an['T3']['delta'])} разрыва точности.",
    "**Согласие голов не заменяет правду под трудным сдвигом.** Ошибки разных голов совпадают чаще, чем при независимых ошибках с теми же частотами "
    f"(Т4 > 0). Самый частый неверный ответ набирает не меньше 3 голосов чаще перестановочного нуля во всех {der['homoplasy_diff_positive']} средах "
    "(точки, без интервала). Там, где ошибки совпали, AGREE заявляет больше всего и почти всегда неверен.",
    "**Возможный механизм (объяснение не проверялось):** на ID согласие голов почти совпадает с верностью, и калибровка на ID учит этой связи; "
    "вне диапазона совпадающие ошибки её ломают.",
    f"**Предложение для оценщика (не проверялось):** вне диапазона ему нужна правда, не зависящая от согласия голов, — проверка кодом или признак "
    f"сдвига во входе, понижающий заявку. Сравнение AGREE с CONF вне диапазона — {n(an['descr_AGREE − CONF']['delta'])} {iv(an['descr_AGREE − CONF']['ci'])} "
    "при 0,005 (описательно): по ИОИ согласие лучше выбора по уверенности, но от POST-CV не отличено (Т2 не решено).",
    "**Область вывода — пять сред теста:** одно семейство сдвига («длина»), сложение, семь открытых голов, подсказка только из ID. "
    "Статус «установлено» — только после повтора с контролем на неспецифичность.",
]
nxt = [
    "**Рекомендация — OCDIV-03 на семействе «тысячи»:** повтор Т4 на втором семействе сдвига тем же кодом, бесплатно на GitHub Actions. "
    f"Пилот 2 «тысячи» уже годен (средний разрыв {n(PIL2['families']['thousands']['drop_mean'])}, годных сред "
    f"{PIL2['families']['thousands']['n_valid']} из 5); его данные опорой не считаются.",
    "**Контроль на неспецифичность для Т4:** нуль со стратами по числу переносов уже есть. Контроль на трудность задачи без утечки правды в нуль — "
    "предмет проекта OCDIV-03, через совет.",
    "**В опись** (новые линии заморожены):",
    "  - оценщик, понижающий заявку по признаку сдвига во входе (длина слагаемого), против AGREE и POST-CV;",
    "  - гомоплазия с интервалом (бутстреп H − H₀) как правило, а не описательно;",
    "  - защита `answer_logp` от служебных токенов (совет 68, п. 0).",
    "**Головы Claude** — после того как автор положит ключ в секрет `ANTHROPIC_API_KEY`: проба API, затем постановка с правдой от кода.",
]
json.dump(dict(short=short, main_question=main_q, next=nxt, council=[]), open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('записано', OUT, OUT_DER)
