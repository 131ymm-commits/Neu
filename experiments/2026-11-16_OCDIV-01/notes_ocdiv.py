#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-01: тексты разделов «Коротко», «Для главного вопроса» и «Что дальше» отчёта. Они написаны после данных теста
(DEVIATIONS п. 3; и после ERRORS № 180). Текст мой; числа подставляются из json счёта тем же форматированием, что в report_ocdiv.py, —
чтобы в тексте не было чисел из памяти. Скрипт пишет report_notes.json рядом с собой, вердиктов не меняет.
  python3 notes_ocdiv.py [ANALYSIS.json FACTS.json OUT.json]
По умолчанию: gha_out/ocdiv_sum_test/analysis.json, gha_out/ocdiv_facts/facts_ocdiv.json, report_notes.json рядом со скриптом."""
import json
import os
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
a = sys.argv[1:]
J = lambda p: json.load(open(p if os.path.isabs(p) else os.path.join(ROOT, p), encoding='utf-8'))  # noqa: E731
an = J(a[0] if a else 'gha_out/ocdiv_sum_test/analysis.json')
fc = J(a[1] if len(a) > 1 else 'gha_out/ocdiv_facts/facts_ocdiv.json')
OUT = a[2] if len(a) > 2 else os.path.join(X, 'report_notes.json')


def n(x, d=4, sign=True):                     # то же, что report_ocdiv.n
    if x is None or x != x:
        return '—'
    s = f'{abs(x):.{d}f}'.replace('.', ',')
    if x < 0 and float(s.replace(',', '.')) != 0:
        return '−' + s
    return ('+' if sign and x > 0 and float(s.replace(',', '.')) != 0 else '') + s


def iv(ci, d=4):
    return f'[{n(ci[0], d)}; {n(ci[1], d)}]'


V = an['verdicts']
assert V['D1'] == 'опровергнуто' and V['D2'] == 'подтверждено' and V['D4'] == 'подтверждено' and V['N'] == 'подтверждено'
assert V['D3'].startswith('не решено') and an['method']['ok'] and not an['crowd_dropped']
nv = an['method']['n_valid']
sc, ib = fc['sign_count'], fc['in_band_count']
pm = fc['parts_mean']
qm, qk, sv = fc['q_mean'], an['q_by_error_kind_descr'], an['same_vendor_descr']
et = fc['err_types_sum']
D = lambda k: an[f'descr_{k}']  # noqa: E731
lit = an['descr_D1 буквальная толпа']
hd = fc['heads']
n_fixed_ob = sum(v == an['fixed_new'] for v in fc['one_best'].values())
up = sorted((nm for nm, h in hd.items() if h['ood'] > h['id']), key=lambda k: -(hd[k]['ood'] - hd[k]['id']))
down = sorted((nm for nm, h in hd.items() if h['ood'] < h['id']), key=lambda k: hd[k]['ood'] - hd[k]['id'])
opp = [nm for nm, h in hd.items() if (h['ood'] - h['id']) * h['ct_ood'] < 0]
same = [nm for nm in hd if nm not in opp]
nm_short = lambda s: s.replace('-Instruct', '').replace('-Chat-v1.0', '').replace('-0425', '')   # noqa: E731

short = [
    f"**D1 опровергнуто:** ошибки разнородной толпы совпадают чаще, чем у шести Pythia. Q-нов − Q-py {n(an['D1']['delta'])}, "
    f"M4 {iv(an['D1']['ci'])}, знак в {sc['D1']['pos']} средах из {sc['D1']['n']}. Это повтор пилота и перенос на p = 2, вес 0. "
    "Вклад производителя не отделён от точности и вида ошибок; объяснение не проверялось.",
    f"**D2 подтверждено:** отбор по наибольшей заявке завышает её и в толпе семи голов пяти производителей. wc CONF {n(an['D2']['delta'])}, "
    f"M4 {iv(an['D2']['ci'])}, {n(an['D2']['z_point'], 1)} s, знак в {sc['D2']['neg']} средах из {sc['D2']['n']}. Это перенос C-090 вне семейства Pythia, "
    "ожидаемо по построению (совет 66); вес 0.",
    f"**D4 и N подтверждены:** вторая калибровка сводит остаток на ID в полосу ±0,02: wc POST {n(an['D4']['delta'])}, M4 {iv(an['D4']['ci'])}; "
    f"у FIXED-нов без отбора {n(an['N']['delta'])}. Это перенос C-100, вес 0. ONE-BEST совпала с FIXED-нов в {n_fixed_ob} средах из {nv}, "
    "как и в OCPOST-01. Поэтому N снова не отделяет поправку от совпадения голов.",
    f"**D3 не решено:** C − T вне диапазона у FIXED-нов {n(an['D3']['delta'])}, M4 {iv(an['D3']['ci'])}. Верхняя граница за полосой +0,02 "
    "(ожидание E8 — 0,67). Калибровка этой головы на ID вне диапазона ни перенеслась в пределах полосы, ни нарушилась за её пределами — "
    "опыт этого не решил.",
    f"**Описательно — вне диапазона эти головы, в отличие от Pythia, не проваливаются.** Точность вне диапазона растёт у {len(up)} голов из "
    f"{len(hd)} и падает у {len(down)} (сильнее всего у OLMo-2: {n(hd['OLMo-2-0425-1B-Instruct']['id'], 4, False)} → "
    f"{n(hd['OLMo-2-0425-1B-Instruct']['ood'], 4, False)}). Оракул {n(fc['oracle_ood_mean']['new'], 4, False)}, T у CONF "
    f"{n(pm['new']['CONF']['T'], 4, False)}; у девяти Pythia — {n(fc['oracle_ood_mean']['py'], 4, False)} и {n(pm['py']['CONF']['T'], 4, False)}. "
    f"Самообман вне диапазона у всех оценщиков мал: CONF {n(pm['new']['CONF']['dec'], 4, False)}, POST-CV {n(pm['new']['POST-CV']['dec'], 4, False)}, "
    f"FIXED {n(pm['new']['FIXED']['dec'], 4, False)} — против {n(pm['py']['CONF']['dec'], 4, False)} у CONF девяти Pythia. Для этих голов сдвиг "
    "диапазона прошлых опытов не означает потерю точности; связь малого самообмана с этим не проверялась.",
]

main_q = [
    "**Отбор обманывает себя и в разнородной толпе, поправка после отбора работает и там.** Оба свойства (C-090 и C-100) вышли за "
    "семейство Pythia: другие головы, другие производители, подсказка p = 2. Это перенос, «ожидаемо по построению»; вес 0, область — эти "
    "семь голов и сложение.",
    f"**Разные производители — не то же, что независимые ошибки.** Когда обе головы пары ошиблись, у разнородной толпы ответы совпадали "
    f"чаще (Q {n(qm['q_new'], 4, False)} против {n(qm['q_py'], 4, False)}). По видам ошибок (описательно): ошибки переноса совпадают часто "
    f"в обеих толпах ({n(qk['перенос нов'], 4, False)} и {n(qk['перенос py'], 4, False)}), прочие — редко ({n(qk['прочее нов'], 4, False)} "
    f"и {n(qk['прочее py'], 4, False)}). Ошибки переноса (лишний перенос и потеря переноса) у новых голов — "
    f"{n(100 * et['нов']['share']['лишний перенос'], 1, False)} % и {n(100 * et['нов']['share']['потеря переноса'], 1, False)} % всех ошибок, у Pythia — "
    f"{n(100 * et['py']['share']['лишний перенос'], 1, False)} % и {n(100 * et['py']['share']['потеря переноса'], 1, False)} %. "
    "Состав ошибок может дать знак D1, но это не проверялось.",
    f"**Для голосования это существенно:** согласие голов (AGREE) ложно, когда ошибшиеся головы дают один и тот же ответ. Общих ошибок у "
    f"этой толпы мало: по всем парам и средам {qm['n_joint_new_sum']} против {qm['n_joint_py_sum']} у пар Pythia (пар 19 и 15). Но когда "
    f"ошиблись обе головы пары, ответ совпадает с долей {n(qm['q_new'], 4, False)}. Вне диапазона разность ИОИ AGREE − CONF {n(an['D5']['delta'])}, "
    f"M4 {iv(an['D5']['ci'])} — ноль не исключён (описательно; знак «AGREE хуже» в {sc['D5']['pos']} средах из {sc['D5']['n']}).",
    f"**Пары одного производителя совпадают в ошибках чаще** пар разных производителей при близкой точности: {n(sv['mean_q_same'], 4, False)} "
    f"против {n(sv['mean_q_cross_matched'], 4, False)} ({sv['n']} сравнений; описательно, вес 0). Это единственная строка, которая хоть как-то "
    "касается вклада производителя; правилом она не была.",
    f"**Описательно: знак C − T вне диапазона у головы противоположен изменению её точности** (семь голов, калибровка на ID). У голов, чья "
    f"точность вне диапазона падает, заявка завышена (OLMo-2: ID {n(hd['OLMo-2-0425-1B-Instruct']['id'], 4, False)} → "
    f"{n(hd['OLMo-2-0425-1B-Instruct']['ood'], 4, False)}, C − T {n(hd['OLMo-2-0425-1B-Instruct']['ct_ood'])}). У голов, чья точность растёт, — "
    f"занижена (TinyLlama: {n(hd['TinyLlama-1.1B-Chat-v1.0']['id'], 4, False)} → {n(hd['TinyLlama-1.1B-Chat-v1.0']['ood'], 4, False)}, "
    f"C − T {n(hd['TinyLlama-1.1B-Chat-v1.0']['ct_ood'])}). Знак C − T противоположен знаку изменения точности у {len(opp)} голов из {len(hd)}"
    + (f" (исключение — {', '.join(nm_short(s) for s in same)})" if same else '') + ". Объяснение не проверялось.",
    f"**Толпа здесь лучше одной головы (описательно, точки).** Вне диапазона незнание у CONF {n(pm['new']['CONF']['ign'], 4, False)}, у ONE-BEST — "
    f"{n(pm['new']['ONE-BEST']['ign'], 4, False)}; ИОИ {n(pm['new']['CONF']['ioi'], 4, False)} против {n(pm['new']['ONE-BEST']['ioi'], 4, False)}. "
    f"У девяти Pythia на тех же задачах наоборот: ИОИ CONF {n(pm['py']['CONF']['ioi'], 4, False)}, ONE-BEST {n(pm['py']['ONE-BEST']['ioi'], 4, False)}. "
    "Бюджеты не равны (семь голов против одной), правилом это не было; описательно.",
]

nxt = [
    "**Головы Claude** — когда ключ API будет в секретах репозитория: та же схема, требования совета 65 (счётчик трат с остановкой, "
    "сухой прогон с ценой вызова, база «одна лучшая голова» и оракул, правда вне доступа голов).",
    "**В опись** (новые линии заморожены):",
    "  - вопрос о производителе — постановка, где точность и вид ошибок пар уравнены заранее: сравнение пар одного и разных производителей "
    "как правило, а не описание;",
    "  - сдвиг, который снижает точность и у этих голов: например, четырёхзначные суммы. Без него вопрос «оценщик вне диапазона» на них не ставится;",
    "  - D3 — на голове с настоящим разрывом ID–OOD; связь C − T вне диапазона с изменением точности — правилом;",
    "  - ложное согласие: доля задач, где большинство ошибшихся голов даёт один неверный ответ, — по видам ошибок.",
]

json.dump(dict(short=short, main_question=main_q, next=nxt), open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('записано', OUT, len(short), len(main_q), len(nxt))
