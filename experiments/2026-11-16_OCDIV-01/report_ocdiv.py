#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка REPORT-OCDIV-01.md: текст — мой, числа — из json счёта на GitHub Actions тем же форматированием, каким их сверяет
ledger.py audit. python3 report_ocdiv.py [ANALYSIS.json FACTS.json EXPECT.json OUT.md]
По умолчанию: gha_out/ocdiv_sum_test/analysis.json, gha_out/ocdiv_facts/facts_ocdiv.json, gha_out/ocdiv_sum_mini/expect_ocdiv.json.
Каркас написан до вывода анализа; разделы «Коротко», «Для главного вопроса» и «Что дальше» — после данных (report_notes.json)."""
import json
import os
import re
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
a = sys.argv[1:]
P_ = lambda p: p if os.path.isabs(p) else os.path.join(ROOT, p)   # noqa: E731
J = lambda p: json.load(open(P_(p), encoding='utf-8'))             # noqa: E731
an_path = a[0] if a else 'gha_out/ocdiv_sum_test/analysis.json'
an = J(an_path)
fp = a[1] if len(a) > 1 else 'gha_out/ocdiv_facts/facts_ocdiv.json'
fc = J(fp) if os.path.exists(P_(fp)) else None
ex = J(a[2] if len(a) > 2 else 'gha_out/ocdiv_sum_mini/expect_ocdiv.json')
OUT = a[3] if len(a) > 3 else os.path.join(X, 'REPORT-OCDIV-01.md')
TLOG = os.path.join(os.path.dirname(P_(an_path)), 'tests.log')
REGHASH, RUNHASH = 'c626aa32', 'dd4d3cc0'
NOTES = {}                                   # тексты разделов «Коротко», «Для главного вопроса», «Что дальше» — после данных
if os.path.exists(os.path.join(X, 'report_notes.json')):
    NOTES = json.load(open(os.path.join(X, 'report_notes.json'), encoding='utf-8'))


def n(x, d=4, sign=True):
    if x is None or x != x:
        return '—'
    s = f'{abs(x):.{d}f}'.replace('.', ',')
    if x < 0 and float(s.replace(',', '.')) != 0:
        return '−' + s
    return ('+' if sign and x > 0 and float(s.replace(',', '.')) != 0 else '') + s


def iv(ci, d=4):
    return f'[{n(ci[0], d)}; {n(ci[1], d)}]' if ci else '—'


def short(nm):
    return nm.split('@')[0]


L = []
add = L.append
RULE_TEXT = {'D1': 'Q-нов − Q-py: совпадение ошибок разнородной толпы минус шесть Pythia',
             'D1 adj': 'δ — D1 с поправкой на точность (описательно)',
             'D2': 'wc CONF разнородной толпы (C-090 вне Pythia)',
             'D3': 'C − T вне диапазона у FIXED-нов (Qwen2.5-0.5B), полоса ±0,02',
             'D4': 'wc POST разнородной толпы, полоса ±0,02 (C-100 вне Pythia)',
             'N': 'wc FIXED-нов, полоса ±0,02 (отрицательный контроль)',
             'D5': 'ИОИ AGREE − ИОИ CONF вне диапазона (описательно)'}
ORDER = ('D1', 'D2', 'D3', 'D4', 'N', 'D5', 'D1 adj')
meth = an.get('method', {})
valid = meth.get('valid', [])
W = (fc or {}).get('weights', {})

add('# OCDIV-01 «ОЦЕНЩИК-РАЗНЫЕ-ГОЛОВЫ» — отчёт (16.11.2026)')
add('')
add('Главный вопрос Neu — оценщик, который не обманывается под давлением отбора. В прежних опытах толпа была из одного семейства '
    '(девять Pythia). Здесь толпа — семь открытых моделей пяти производителей. Проверяется, реже ли совпадают их ошибки и переносятся ли '
    'на такую толпу C-090 (wc CONF < 0: отбор завышает заявку) и C-100 (wc POST в полосе: вторая калибровка снимает завышение на ID).')
add(f'- **Предрегистрация — коммит {REGHASH}** (`PREREG-OCDIV-01.md`; совет 66 — три линзы, 4 «за» из 4). Запуск теста — коммит {RUNHASH}.')
add('- **Данные** — GitHub Actions, процессор раннера: 35 заданий (7 голов × 5 сред OCPOST-01, X = 4…8, подсказка p = 2), в каждой среде '
    f"{n(an['envs'][valid[0]]['n_id'] + an['envs'][valid[0]]['n_ood'], 0, False) if valid else '—'} задач. Ответы девяти Pythia — сырой вывод OCPOST-01 на тех же задачах.")
add(f"- **Счёт** — GitHub Actions: анализ (`gha_out/ocdiv_sum_test/analysis.json`, B = {n(an['B'], 0, False)}), производные числа и вес опоры "
    "(`gha_out/ocdiv_facts/facts_ocdiv.json`).")
add('')
add('## Итог')
add('')
add('| Правило | Что | Точка | M4 при 0,0025 | Δ/s | интервал в s | z\\* | Вердикт | Вес опоры |')
add('|---|---|---|---|---|---|---|---|---|')
for k in ORDER:
    e = an.get(k)
    if not e:
        add(f"| {k} | {RULE_TEXT[k]} | — | — | — | — | — | {an.get('verdicts', {}).get(k, '—')} | — |")
        continue
    v = e['verdict']
    if e.get('verdict_rule_descr'):
        v = f"{v}; по правилу было бы «{e['verdict_rule_descr']}»"
    if e.get('sensitive_to_level'):
        v += ' — чувствителен к уровню'
    w = W.get(k, {}).get('bits') if k in W else (0.0 if k == 'D1 adj' else None)
    ws = '—' if (k not in W and k != 'D1 adj') else ('не определён' if w is None else n(w, 2, False) + ' бит')
    add(f"| {k} | {RULE_TEXT[k]} | {n(e['delta'])} | {iv(e['ci'])} | {n(e['z_point'], 1)} | {iv(e.get('ci_in_s'), 1)} | {n(e['z_star'], 1, False)} | {v} | {ws} |")
add('')
add('- Все веса этого опыта — верхняя оценка, не для реестра (PREREG §10): перенос M4 на уровень 0,0025 для среднего пяти сред не проверен. '
    'z\\* — z, при котором меняется вердикт; пометка «чувствителен к уровню» — при z\\* < 2,807 × 1,5.')
for k in ('D1', 'D2', 'D5', 'D1 adj'):
    g = (an.get(k) or {}).get('leave_one_range_out')
    if g:
        add(f"- {k}: знак среднего без одной среды сохраняется — {'да' if g.get('holds') else 'нет'}; сред того же знака {g.get('n_same_sign')} из {g.get('n')}.")
add('')
if NOTES.get('short'):
    add('**Коротко.**')
    for s_ in NOTES['short']:
        add(f'- {s_}')
    add('')
add('**Метод опыта.**')
add(f"- Годных сред {meth.get('n_valid')} из {meth.get('n_envs')}; опыт определён — {'да' if meth.get('ok') else 'нет'}. "
    f"FIXED-нов в толпе всех годных сред — {'да' if meth.get('fixed_in_all_valid') else 'нет'}.")
drop = an.get('crowd_dropped') or {}
add(f"- Толпа: {len(an.get('crowd_effective', []))} голов из {len(an.get('crowd', {}))}; "
    + ('выбывших по ревизии и версиям нет.' if not drop else 'выбыли: ' + '; '.join(f'{k} — {v}' for k, v in drop.items()) + '.'))
add(f"- Сборка: ключи задач и подсказки сверены с источником — {'да' if an.get('keys_checked') else 'нет'}; "
    f"ошибок загрузки голов — {len(an.get('head_errors') or [])}.")
if os.path.exists(TLOG):
    tl = open(TLOG, encoding='utf-8').read()
    ok_, bad_ = len(re.findall(r'^✓', tl, re.M)), len(re.findall(r'^✗', tl, re.M))
    add(f'- Тесты кода в задании анализа: пройдено {ok_}, провалено {bad_} (`gha_out/ocdiv_sum_test/tests.log`).')
cpu = sorted({c for v in (an.get('cpu_models') or {}).values() for c in (v or [])})
if cpu:
    add(f"- Процессоры раннеров: {'; '.join(cpu)}.")
add(f"- Время анализа — {n(an.get('seconds'), 0, False)} с.")
add('')
add('| Среда | задач ID | задач OOD | голов в толпе | годна |')
add('|---|---|---|---|---|')
for nm, e in sorted(an['envs'].items()):
    add(f"| {nm} | {e['n_id']} | {e['n_ood']} | {len(e['crowd'])} из {e['n_crowd_heads']} | {'да' if e['valid'] else 'нет'} |")
add('')
add('## Правила чтения (записаны до данных)')
d1 = an.get('D1', {})
if d1.get('reading'):
    add(f"- **D1:** {d1['reading']}.")
for k in ('D2', 'D4'):
    if an.get(k, {}).get('class'):
        add(f"- **{k}:** класс — {an[k]['class']}; точка в единицах s — {n(an[k]['z_point'], 1)}.")
d3 = an.get('D3', {})
if d3:
    add(f"- **D3:** знак — {d3.get('sign')}; {d3.get('reading')}.")
if an.get('D4') and an.get('D2'):
    v2, v4, vN = an['D2']['verdict'], an['D4']['verdict'], an['N']['verdict']
    if v4 == 'подтверждено':
        add('- **D4 при D2:** ' + ('вторая калибровка снимает самообман на ID и у разнородной толпы (перенос).' if v2 == 'подтверждено'
                                   else 'D2 не подтверждено: wc POST «в полосе», а не «снят».'))
    if vN != 'подтверждено':
        add('- **N не подтверждён:** к D4 добавляется — несмещённость счёта T − C без отбора не показана.')
add('')
if fc:
    add('## Головы толпы (среднее по годным средам; описательно)')
    add('')
    add('| Голова | Производитель | точность ID | точность OOD | C − T вне диапазона |')
    add('|---|---|---|---|---|')
    for nm, h in fc['heads'].items():
        add(f"| {nm} | {h['vendor']} | {n(h['id'], 4, False)} | {n(h['ood'], 4, False)} | {n(h['ct_ood'])} |")
    add('')
    ob = fc.get('one_best', {})
    add('- ONE-BEST (наибольшая точность на ID) по средам: ' + '; '.join(f'{k} — {v}' for k, v in ob.items()) + '.')
    add('')
add('## По средам (точка и ст. откл. повторов)')
add('')
add('| Среда | Q-нов | Q-py | D1 | D2 | D3 | D4 | N | D5 |')
add('|---|---|---|---|---|---|---|---|---|')
for nm in valid:
    e = an['envs'][nm]
    re_ = e['rules_env']
    add(f"| {nm} | {n(e['q']['q_new'], 4, False)} | {n(e['q']['q_py'], 4, False)} | "
        + ' | '.join(f"{n(re_[k]['point'])} ({n(re_[k]['sd'], 4, False)})" for k in ('D1', 'D2', 'D3', 'D4', 'N', 'D5')) + ' |')
add('')
if fc:
    sc, ib = fc['sign_count'], fc['in_band_count']
    add(f"- Знак по средам: D1 > 0 — в {sc['D1']['pos']} из {sc['D1']['n']}; D2 < 0 — в {sc['D2']['neg']} из {sc['D2']['n']}; "
        f"D5 > 0 — в {sc['D5']['pos']} из {sc['D5']['n']}. В полосе ±0,02: D3 — {ib['D3']}, D4 — {ib['D4']}, N — {ib['N']} сред из {len(valid)}.")
    add('')
add('## Совпадение ошибок (описательно, вес 0)')
add('')
sv = an.get('same_vendor_descr') or {}
if sv:
    add(f"- **Главная описательная строка (совет 66).** Пары одного производителя (две Qwen, две SmolLM) против пар разных производителей "
        f"с точностью пары в пределах ±0,05: q одного производителя — {n(sv.get('mean_q_same'), 4, False)}, q разных при близкой точности — "
        f"{n(sv.get('mean_q_cross_matched'), 4, False)} (пар со сравнением: {sv.get('n')}).")
qk = an.get('q_by_error_kind_descr') or {}
if qk:
    add(f"- **q по типу ошибки** (обе головы ошиблись одинаковым типом): перенос — разнородная {n(qk.get('перенос нов'), 4, False)}, Pythia "
        f"{n(qk.get('перенос py'), 4, False)}; прочее — разнородная {n(qk.get('прочее нов'), 4, False)}, Pythia {n(qk.get('прочее py'), 4, False)}.")
lit = an.get('descr_D1 буквальная толпа')
if lit:
    add(f"- **D1 для толпы по буквальному отбору «20 и 20»** ({len(lit.get('crowd', []))} голов): {n(lit['delta'])}, M4 при 0,005 — {iv(lit['ci'])}.")
d1a = an.get('D1 adj')
if d1a and fc:
    add(f"- **δ** (поправка на точность): {n(d1a['delta'])}, M4 при 0,0025 — {iv(d1a['ci'])}; β в среднем по средам {n(fc['q_mean']['adj_beta'])}.")
if fc:
    qm = fc['q_mean']
    add(f"- Среднее по средам: Q-нов {n(qm['q_new'], 4, False)}, Q-py {n(qm['q_py'], 4, False)}, q пар «новая голова — Pythia» "
        f"{n(qm['q_cross_descr'], 4, False)}; общих ошибок у пар — {qm['n_joint_new_sum']} (разнородная) и {qm['n_joint_py_sum']} (Pythia).")
    et = fc.get('err_types_sum', {})
    for side, lab in (('нов', 'разнородная толпа'), ('py', 'шесть Pythia')):
        e_ = et.get(side)
        if e_ and e_['total']:
            add(f"- Типы ошибок ({lab}, все головы, числовые ответы; {e_['total']} ошибок): "
                + '; '.join(f"{t} — {c} ({n(100 * e_['share'][t], 1, False)} %)" for t, c in sorted(e_['counts'].items(), key=lambda kv: -kv[1])) + '.')
add('')
if fc:
    add('## Незнание и самообман отдельно (вне диапазона; среднее по годным средам, точки)')
    add('')
    add('| Толпа | Оценщик | T (доля верных) | C (средняя заявка) | незнание 1 − T | самообман max(0, C − T) | ИОИ | Брайер |')
    add('|---|---|---|---|---|---|---|---|')
    for cr, lab in (('new', 'разнородная (7)'), ('py', 'девять Pythia'), ('mix', 'смешанная (16)')):
        for e_ in ('CONF', 'POST-CV', 'ONE-BEST', 'FIXED', 'SHIFT', 'AGREE'):
            p_ = fc['parts_mean'][cr][e_]
            if p_['T'] is None:
                continue
            add(f"| {lab} | {e_} | {n(p_['T'], 4, False)} | {n(p_['C'], 4, False)} | {n(p_['ign'], 4, False)} | {n(p_['dec'], 4, False)} | "
                f"{n(p_['ioi'], 4, False)} | {n(p_['brier'], 4, False)} |")
    om = fc['oracle_ood_mean']
    add('')
    add(f"- Оракул вне диапазона (верна хоть одна голова): разнородная {n(om['new'], 4, False)}, девять Pythia {n(om['py'], 4, False)}, "
        f"смешанная {n(om['mix'], 4, False)}. FIXED у девяти Pythia — pythia-2.8b-deduped, у разнородной и смешанной — Qwen2.5-0.5B.")
    add('')
add('## Описательно (вес 0; M4 при 0,005)')
add('')
add('| Разность | Точка | M4 при 0,005 |')
add('|---|---|---|')
for k, e in an.items():
    if k.startswith('descr_') and k != 'descr_D1 буквальная толпа':
        add(f"| {k[6:]} | {n(e['delta'])} | {iv(e['ci'])} |")
add('')
OUTCOME = {'E1': ('D1', 'опровергнуто'), 'E2': ('D2', 'подтверждено'), 'E3': ('D3', 'опровергнуто'), 'E4': ('D3', 'подтверждено'),
           'E5': ('D4', 'подтверждено'), 'E6': ('N', 'подтверждено'), 'E8': ('D3', 'не решено')}
add('## Ожидания (PREREG §6; исход — по вердиктам выше)')
add('')
add('| № | Исход | Вероятность до прогона | Сбылось |')
add('|---|---|---|---|')
for e in ex['expect']:
    if e['id'] == 'E7':
        hit = bool(meth.get('ok'))
    else:
        k, want = OUTCOME[e['id']]
        hit = an.get('verdicts', {}).get(k) == want
    add(f"| {e['id']} | {e['text']}{' (тривиальное)' if e.get('trivial') else ''} | {n(e['p'], 3, False)} | {'да' if hit else 'нет'} |")
add('')
for sec, title in (('main_question', 'Для главного вопроса'), ('next', 'Что дальше')):
    if NOTES.get(sec):
        add(f'## {title}')
        add('')
        for s_ in NOTES[sec]:
            add(f'- {s_}')
        add('')
if W:
    add('## Вес опоры (PREREG §10; верхняя оценка, не для реестра)')
    add('')
    for k in ('D1', 'D2', 'D3', 'D4', 'N', 'D5'):
        w = W[k]
        add(f"- {k}: {w['verdict']}; вес {('не определён' if w['bits'] is None else n(w['bits'], 2, False) + ' бит')}"
            + (f"; мощность {n(w['power'], 3, False)}" if w.get('power') is not None else '') + (f"; {w['note']}" if w.get('note') else '') + '.')
    add('')
add('## Отклонения')
add('')
add('См. `DEVIATIONS.md`.' if os.path.exists(os.path.join(X, 'DEVIATIONS.md')) else 'Нет.')
open(OUT, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('записано', OUT, len(L), 'строк')
