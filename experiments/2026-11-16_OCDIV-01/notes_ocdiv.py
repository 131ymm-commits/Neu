#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-01: тексты разделов «Коротко», «Для главного вопроса» и «Что дальше» отчёта. Они написаны после данных теста
(DEVIATIONS п. 3; и после ERRORS № 180) и правлены по совету 67. Текст мой; числа подставляются из json счёта тем же форматированием,
что в report_ocdiv.py, — чтобы в тексте не было чисел из памяти. Производные числа (отношения, средние по головам, биномиальный
хвост, ложный уровень серии по формуле PREREG §7) считаются здесь же и пишутся в report_derived.json — его читает отчёт и ledger.py audit.
Скрипт вердиктов не меняет.
  python3 notes_ocdiv.py [ANALYSIS.json FACTS.json OUT.json]
По умолчанию: gha_out/ocdiv_sum_test/analysis.json, gha_out/ocdiv_facts/facts_ocdiv.json, report_notes.json рядом со скриптом."""
import json
import os
import sys
from math import comb

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
a = sys.argv[1:]
J = lambda p: json.load(open(p if os.path.isabs(p) else os.path.join(ROOT, p), encoding='utf-8'))  # noqa: E731
an = J(a[0] if a else 'gha_out/ocdiv_sum_test/analysis.json')
fc = J(a[1] if len(a) > 1 else 'gha_out/ocdiv_facts/facts_ocdiv.json')
OUT = a[2] if len(a) > 2 else os.path.join(X, 'report_notes.json')
DER = os.path.join(X, 'report_derived.json')


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
sc = fc['sign_count']
pm = fc['parts_mean']
qm, qk, sv = fc['q_mean'], an['q_by_error_kind_descr'], an['same_vendor_descr']
et = fc['err_types_sum']
hd = fc['heads']
n_fixed_ob = sum(v == an['fixed_new'] for v in fc['one_best'].values())
up = [nm for nm, h in hd.items() if h['ood'] > h['id']]
down = [nm for nm, h in hd.items() if h['ood'] < h['id']]
opp = [nm for nm, h in hd.items() if (h['ood'] - h['id']) * h['ct_ood'] < 0]
same = [nm for nm in hd if nm not in opp]
nm_short = lambda s: s.replace('-Instruct', '').replace('-Chat-v1.0', '').replace('-0425', '')   # noqa: E731
OL, TL, FA = hd['OLMo-2-0425-1B-Instruct'], hd['TinyLlama-1.1B-Chat-v1.0'], hd['Falcon3-1B-Instruct']
k_n = len(hd)
n_pairs_new = sum(1 for p in an['envs'][an['method']['valid'][0]]['q']['pairs'] if p['kind'] == 'нов')
n_pairs_py = sum(1 for p in an['envs'][an['method']['valid'][0]]['q']['pairs'] if p['kind'] == 'py')
level = an['level']
der = dict(
    source='notes_ocdiv.py: производные analysis.json и facts_ocdiv.json; формулы — в ключах «как»',
    joint_ratio=dict(value=qm['n_joint_py_sum'] / qm['n_joint_new_sum'], как='n_joint_py_sum / n_joint_new_sum (суммы по пяти средам; пар 15 и 19)'),
    joint_per_pair=dict(new=qm['n_joint_new_sum'] / n_pairs_new, py=qm['n_joint_py_sum'] / n_pairs_py, как='сумма совместных ошибок / число пар'),
    n_pairs=dict(new=n_pairs_new, py=n_pairs_py, all_new=comb(k_n, 2), same_vendor=comb(k_n, 2) - n_pairs_new),
    acc_mean_heads=dict(id=sum(h['id'] for h in hd.values()) / k_n, ood=sum(h['ood'] for h in hd.values()) / k_n, как='среднее по семи головам'),
    olmo_drop=dict(value=OL['id'] - OL['ood'], как='точность ID − OOD у OLMo-2'),
    falcon_drop=dict(value=FA['id'] - FA['ood'], как='точность ID − OOD у Falcon3'),
    sign_opp=dict(k=len(opp), n=k_n, p_one_sided=sum(comb(k_n, j) for j in range(len(opp), k_n + 1)) / 2 ** k_n,
                  как='P(не меньше k из n при p = 0,5), точный биномиальный хвост'),
    series_false=dict(confirm=6 * level, any=11 * level, как='PREREG §7: 6 × 0,0025 (D3 — с двух сторон полосы) и 11 × 0,0025'),
)
json.dump(der, open(DER, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
R = der['joint_ratio']['value']
PH = ' *(пост-хок: выбрано и написано после просмотра сырого вывода, ERRORS № 180)*'

short = [
    f"**D1 опровергнуто:** когда ошиблись обе головы пары, ответы разнородной толпы совпадают чаще, чем у шести Pythia. Q-нов − Q-py "
    f"{n(an['D1']['delta'])}, M4 {iv(an['D1']['ci'])}, знак в {sc['D1']['pos']} средах из {sc['D1']['n']}. q — доля совпавших ответов среди "
    f"совместных ошибок, а не частота совместных ошибок. Совместных ошибок у разнородной толпы в {n(R, 1, False)} раза меньше по сумме: "
    f"{qm['n_joint_new_sum']} на {n_pairs_new} пар против {qm['n_joint_py_sum']} на {n_pairs_py} пар Pythia. D1 не значит «разнообразие вредит». "
    "Это повтор пилота и перенос на p = 2, вес 0; вклад производителя не отделён от точности и вида ошибок, объяснение не проверялось.",
    f"**D2 подтверждено:** отбор по наибольшей заявке завышает её и в толпе семи голов пяти производителей. wc CONF {n(an['D2']['delta'])}, "
    f"M4 {iv(an['D2']['ci'])}, {n(an['D2']['z_point'], 1)} s, знак в {sc['D2']['neg']} средах из {sc['D2']['n']}. Это перенос C-090 вне семейства Pythia, "
    "ожидаемо по построению (совет 66); вес 0.",
    f"**D4 и N подтверждены:** вторая калибровка сводит остаток на ID в полосу ±0,02: wc POST {n(an['D4']['delta'])}, M4 {iv(an['D4']['ci'])}; "
    f"у FIXED-нов без отбора {n(an['N']['delta'])}. Это перенос C-100, вес 0. ONE-BEST совпала с FIXED-нов в {n_fixed_ob} средах из {nv}, "
    "как и в OCPOST-01: N не отделяет поправку от совпадения голов.",
    f"**D3 не решено:** C − T вне диапазона у FIXED-нов {n(an['D3']['delta'])}, M4 {iv(an['D3']['ci'])}. Верхняя граница за полосой +0,02 "
    "(ожидание E8 — 0,67). Перенеслась ли калибровка этой головы на ID за пределы диапазона, опыт не решил.",
    f"**Описательно{PH}: на этом сдвиге (X = 4…8, p = 2) средняя точность голов вне диапазона не падает** — "
    f"{n(der['acc_mean_heads']['id'], 4, False)} на ID и {n(der['acc_mean_heads']['ood'], 4, False)} вне диапазона (среднее по семи головам). "
    f"Падает она у {len(down)} голов из {k_n} (больше всего у OLMo-2 — на {n(der['olmo_drop']['value'], 4, False)}). Для этих голов этот диапазон "
    f"не является сдвигом. **Потолок:** вне диапазона T у CONF {n(pm['new']['CONF']['T'], 4, False)}, поэтому самообман не больше незнания "
    f"1 − T = {n(pm['new']['CONF']['ign'], 4, False)}. Самообман CONF {n(pm['new']['CONF']['dec'], 4, False)}, POST-CV {n(pm['new']['POST-CV']['dec'], 4, False)}, "
    f"FIXED {n(pm['new']['FIXED']['dec'], 4, False)}. С девятью Pythia (T {n(pm['py']['CONF']['T'], 4, False)}) по величине самообмана "
    "это не сравнимо: разные уровни точности (совет 67).",
]

main_q = [
    "**Отбор обманывает себя и в разнородной толпе; поправка после отбора работает и там** (правила D2 и D4). Оба свойства — C-090 и C-100 — "
    "перенесены за семейство Pythia: другие головы, другие производители, подсказка p = 2. Это перенос, «ожидаемо по построению», вес 0. "
    "Область статуса «установлено», который дал совет 65, не расширяется (совет 67).",
    f"**Совпадение ошибок по видам.** Таблица q по видам ошибок — описательная строка PREREG §5, записанная до данных; толкование ниже — "
    f"пост-хок. В этой смеси видов ошибок совпадение выше. Внутри ошибок переноса оно ниже, чем у Pythia ({n(qk['перенос нов'], 4, False)} "
    f"против {n(qk['перенос py'], 4, False)}), в слое «прочее» — выше ({n(qk['прочее нов'], 4, False)} против {n(qk['прочее py'], 4, False)}). "
    f"Ошибки переноса у новых голов — {n(100 * et['нов']['share']['лишний перенос'], 1, False)} % (лишний перенос) и "
    f"{n(100 * et['нов']['share']['потеря переноса'], 1, False)} % (потеря переноса) всех ошибок, у Pythia — "
    f"{n(100 * et['py']['share']['лишний перенос'], 1, False)} % и {n(100 * et['py']['share']['потеря переноса'], 1, False)} %. "
    "Состав видов ошибок сдвигает итог, но знак D1 держится и в слое «прочее». Объяснение не проверялось. У совета 67 две версии: "
    "состав видов ошибок (интуит) и разные знаменатели q, то есть разная точность толп (формалист); обе — в опись.",
    f"**Пары одного производителя** (описательная строка PREREG §5; толкование — пост-хок) совпадают в ошибках чаще пар разных производителей "
    f"при близкой точности: {n(sv['mean_q_same'], 4, False)} против {n(sv['mean_q_cross_matched'], 4, False)}. Сравнений {sv['n']}, пары не "
    "независимы (делят головы), производителей с парой всего два. Правилом это не было; вес 0.",
    f"**Знак C − T вне диапазона против изменения точности{PH} — ожидаемо по построению калибровки на ID.** Заявка настроена на точность ID, "
    "поэтому вне диапазона C − T примерно равно разрыву точности ID − OOD. "
    f"Пример: OLMo-2 — {n(OL['id'], 4, False)} → {n(OL['ood'], 4, False)}, C − T {n(OL['ct_ood'])}; TinyLlama — {n(TL['id'], 4, False)} → "
    f"{n(TL['ood'], 4, False)}, C − T {n(TL['ct_ood'])}. Знак противоположен у {len(opp)} голов из {k_n}: при p = 0,5 одностороннее p = "
    f"{n(der['sign_opp']['p_one_sided'], 4, False)} (точный биномиальный хвост). Исключение — "
    + ', '.join(nm_short(s) for s in same) + f": точность падает ({n(FA['id'], 4, False)} → {n(FA['ood'], 4, False)}), а C − T {n(FA['ct_ood'])}. "
    "Находкой это не считается.",
    f"**Толпа из семи голов против одной{PH}:** бюджет 7:1. Вне диапазона незнание у CONF {n(pm['new']['CONF']['ign'], 4, False)}, у ONE-BEST — "
    f"{n(pm['new']['ONE-BEST']['ign'], 4, False)}; оракул {n(fc['oracle_ood_mean']['new'], 4, False)} — у потолка. Сравнения при равном бюджете "
    "нет; к главному вопросу это не относится.",
]

nxt = [
    "**Первым из описи** (совет 67, единогласно) — сдвиг, при котором точность и у этих голов падает: например, четырёхзначные суммы на тех же "
    "семи головах. Около 35 заданий на процессоре раннеров, без денег. Без такого сдвига вопрос «оценщик вне диапазона» и D3 на этих головах "
    "упираются в потолок. В тот же PREREG:",
    "  - безусловная доля задач, где обе головы ошиблись одним ответом, с разбивкой по видам ошибок, заданной заранее;",
    "  - доля задач, где неверный ответ набрал не меньше голосов, чем верный, против перестановочного нуля;",
    "  - доля разрыва ID–OOD, которую снимает калибровка (OCDIV-01 для неё — только пилот);",
    "  - D3 на голове с разрывом ID–OOD не меньше 0,1;",
    "  - мощность — симуляцией до прогона; время на задачу у самой медленной головы — пилотом на сиде вне теста.",
    "**Головы Claude** — после этого или параллельно, на том же трудном сдвиге. Условия: ключ API автора в секретах репозитория, счётчик "
    "трат с остановкой, сухой прогон с ценой вызова.",
]

json.dump(dict(short=short, main_question=main_q, next=nxt), open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('записано', OUT, len(short), len(main_q), len(nxt), '|', DER)
