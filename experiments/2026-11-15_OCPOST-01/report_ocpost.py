#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка REPORT-OCPOST-01.md: текст — мой, числа — из json счёта на GitHub Actions тем же форматированием, каким их сверяет
ledger.py audit. python3 report_ocpost.py [ANALYSIS.json TAIL.json FACTS.json OUT.md]
По умолчанию: gha_out/ocpost_test/analysis.json, gha_out/ocpost_tail_sum/tail.json, gha_out/ocpost_facts/facts_ocpost.json.
Каркас написан до данных теста; разделы «Коротко», «Для главного вопроса» и «Что дальше» дописываются после данных (NOTES ниже)."""
import json
import os
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
a = sys.argv[1:]
J = lambda p: json.load(open(p if os.path.isabs(p) else os.path.join(ROOT, p), encoding='utf-8'))  # noqa: E731
an = J(a[0] if a else 'gha_out/ocpost_test/analysis.json')
tp = a[1] if len(a) > 1 else 'gha_out/ocpost_tail_sum/tail.json'
fp = a[2] if len(a) > 2 else 'gha_out/ocpost_facts/facts_ocpost.json'
tl = J(tp) if os.path.exists(tp if os.path.isabs(tp) else os.path.join(ROOT, tp)) else None
fc = J(fp) if os.path.exists(fp if os.path.isabs(fp) else os.path.join(ROOT, fp)) else None
OUT = a[3] if len(a) > 3 else os.path.join(X, 'REPORT-OCPOST-01.md')
REGHASH, RAWHASH = '8ccae4a4', 'f4dc1ba9'
NOTES = {}                                   # тексты разделов «Коротко», «Для главного вопроса», «Что дальше» — после данных
if os.path.exists(os.path.join(X, 'report_notes.json')):
    NOTES = json.load(open(os.path.join(X, 'report_notes.json'), encoding='utf-8'))


def n(x, d=4, sign=True):
    if x is None:
        return '—'
    s = f'{abs(x):.{d}f}'.replace('.', ',')
    if x < 0 and float(s.replace(',', '.')) != 0:
        return '−' + s
    return ('+' if sign and x > 0 and float(s.replace(',', '.')) != 0 else '') + s


def iv(ci, d=4):
    return f'[{n(ci[0], d)}; {n(ci[1], d)}]'


L = []
add = L.append
RULE_TEXT = {'P0': 'wc CONF (повтор C-090)', 'P1': 'ИОИ POST-CV − ИОИ CONF', 'P2': 'ИОИ POST-CV − ИОИ ONE-BEST',
             'P3': 'wc POST (полоса ±0,02)', 'N': 'wc FIXED (полоса ±0,02)'}
valid = an['method']['valid']
add('# OCPOST-01 «ОЦЕНЩИК-ПОСЛЕ-ОТБОРА» — отчёт (15–16.11.2026)')
add('')
add('Главный вопрос Neu — оценщик, который не обманывается под давлением отбора. Здесь проверяется вторая калибровка после отбора: '
    'отображение «выбранная заявка → верен ли выбранный ответ», выученное на ID вне частей кросс-подгонки.')
add(f'- **Предрегистрация — коммит {REGHASH}** (`PREREG-OCPOST-01.md`; совет 64 — три линзы, принято единогласно).')
add(f"- **Данные** — Kaggle, T4 × 2, одна попытка: {(an['sources'][0].get('info') or {}).get('n_gpu', '—')} видеокарты, сырой вывод — коммит {RAWHASH} "
    f"(`run/out/answers.json`). Пять свежих сред (X = 4…8, подсказка p = 2), по 2200 задач; девять голов Pythia.")
add('- **Счёт** — GitHub Actions: анализ теста (`gha_out/ocpost_test/analysis.json`), проверка хвоста Т (`gha_out/ocpost_tail_a`, '
    '`gha_out/ocpost_tail_b`, сводка — `gha_out/ocpost_tail_sum/tail.json`), вес опоры — `gha_out/ocpost_facts/facts_ocpost.json`.')
add('')
add('## Итог')
add('')
add('| Правило | Что | Точка | M4 при 0,0025 | Вердикт | Вес опоры |')
add('|---|---|---|---|---|---|')
for k in ('P0', 'P1', 'P2', 'P3', 'N'):
    e = an[k]
    w = fc['weights'][k]['bits'] if fc else None
    add(f"| {k} | {RULE_TEXT[k]} | {n(e['delta'])} | {iv(e['ci'])} | {e['verdict']} | {('—' if w is None else n(w, 2, False) + ' бит')} |")
if tl:
    add(f"| Т | хвост M4 на свежих мирах ({tl['n_worlds']} миров) | — | — | {tl['verdict']} | 0 бит (проверка метода) |")
else:
    add('| Т | хвост M4 на свежих мирах | — | — | ждёт счёта | — |')
add('')
if NOTES.get('short'):
    add('**Коротко.**')
    for s_ in NOTES['short']:
        add(f'- {s_}')
    add('')
add('**Метод опыта.**')
ch = an.get('check') or {}
add(f"- Сверка цепочки с выводом OCREP-01: ответы совпали — {'да' if ch.get('answers_equal') else 'нет'}, наибольшее расхождение logp "
    f"{n(ch.get('max_abs_dlogp', 0), 6, False)} (допуск 0,001). Годных сред {an['method']['n_valid']} из {an['method']['n_envs']}; "
    f"голова FIXED в толпе всех годных сред — {'да' if an['method']['fixed_in_all_valid'] else 'нет'}.")
add(f"- Бутстреп: B = {an['B']} повторов на среду; время анализа — {n(an['seconds'], 0, False)} с.")
add('')
add('## Правила чтения (записаны до данных)')
r1, r2 = an['P1'].get('brier_reading', {}), an['P2'].get('brier_reading', {})
r2d = an['P2'].get('ood_deception_reading', {})
add(f"- **P1 и Брайер:** разность Брайера POST-CV − CONF, M4 при 0,0025 — {iv(r1.get('ci', [None, None]))}; по Брайеру POST-CV {r1.get('side', '—')}."
    + (f" Запись: «{r1['note']}»." if r1.get('note') else ''))
add(f"- **P2 и Брайер:** разность Брайера POST-CV − ONE-BEST — {iv(r2.get('ci', [None, None]))}; по Брайеру POST-CV {r2.get('side', '—')}."
    + (f" Запись: «{r2['note']}»." if r2.get('note') else ''))
add(f"- **P2 и самообман вне диапазона:** разность самообмана POST-CV − ONE-BEST — {iv(r2d.get('ci', [None, None]))}"
    + (f"; запись: «{r2d['note']}»." if r2d.get('note') else '; чтение не применяется.'))
if an['P2']['verdict'].startswith('не решено'):
    add(f"- **P2:** {an['P2'].get('note', '')}.")
add(f"- **P3:** {an['P3'].get('reading', '')}.")
fs = an['N'].get('fixed_split_descr', {})
add(f"- **N:** {fs.get('note', '')}. ONE-BEST = FIXED в {fs.get('n_same')} средах из {an['method']['n_valid']}; wc FIXED в этих средах — "
    f"{n(fs.get('wc_fixed_same'))}, в остальных — {n(fs.get('wc_fixed_other'))}.")
add('')
add('## Незнание и самообман отдельно (вне диапазона; среднее по годным средам, точки)')
add('')
add('| Оценщик | T (доля верных) | C (средняя заявка) | незнание 1 − T | самообман max(0, C − T) | ИОИ | Брайер |')
add('|---|---|---|---|---|---|---|')
for e_ in ('CONF', 'POST-CV', 'ONE-BEST', 'FIXED', 'SHIFT'):
    if fc:
        p_ = fc['parts_mean'][e_]
        add(f"| {e_} | {n(p_['T'], 4, False)} | {n(p_['C'], 4, False)} | {n(p_['ign'], 4, False)} | {n(p_['dec'], 4, False)} | {n(p_['ioi'], 4, False)} | {n(p_['brier'], 4, False)} |")
add('')
add('## По средам (точка и ст. откл. повторов)')
add('')
add('| Среда | P0 | P1 | P2 | P3 | N | ONE-BEST |')
add('|---|---|---|---|---|---|---|')
for nm in valid:
    re_ = an['envs'][nm]['rules_env']
    add(f"| {nm} | " + ' | '.join(f"{n(re_[k]['point'])} ({n(re_[k]['sd'], 4, False)})" for k in ('P0', 'P1', 'P2', 'P3', 'N'))
        + f" | {an['envs'][nm]['extras']['one_best']} |")
add('')
for k in ('P0', 'P1', 'P2'):
    g = an[k].get('leave_one_range_out', {})
    if g:
        add(f"- {k}: знак среднего без одного диапазона сохраняется — {'да' if g.get('holds') else 'нет'}; сред того же знака {g.get('n_same_sign')} из {g.get('n')}.")
add('')
if tl:
    add('## Т — хвост M4 на свежих мирах')
    add('')
    add(f"Зерно {tl['meta']}, миры {min(tl['worlds'])}–{max(tl['worlds'])}; промахи M4 при 0,0025 по сторонам; верхняя граница Клоппера — Пирсона уровня 0,0025.")
    add('')
    add('| Статистика | опытов | NaN | промахов снизу | верхняя граница | промахов сверху | верхняя граница | ст. откл. повторов / истинное | среднее по 5 мирам: снизу / сверху из |')
    add('|---|---|---|---|---|---|---|---|---|')
    for s_, e in tl['stats'].items():
        md = tl['mean_of_5_descr'][s_]
        add(f"| {s_} | {e['n']} | {e['n_nan']} | {e['miss_low']} | {n(e['upper_low'], 4, False)} | {e['miss_high']} | {n(e['upper_high'], 4, False)} | "
            f"{n(e['sd_ratio_mean'], 3, False)} | {md['miss_low']} / {md['miss_high']} из {md['n']} |")
    add('')
add('## Описательно (вес 0; M4 при 0,005)')
add('')
add('| Разность | Точка | M4 при 0,005 |')
add('|---|---|---|')
for k, e in an.items():
    if k.startswith('descr_'):
        add(f"| {k[6:]} | {n(e['delta'])} | {iv(e['ci'])} |")
het = an['P2'].get('heterogeneity_descr')
if het:
    add('')
    add(f"- Неоднородность P2 по средам: Q {n(het['Q'], 2, False)} при {het['df']} степенях свободы, p χ² {het['p_chi2']:.2e}.")
dm = an['P2'].get('dominance_descr')
if dm:
    add(f"- Связь P2 среды с отрывом лучшей головы на ID: ранговая корреляция {n(dm['spearman'], 3)} (n = {dm['n']}; описательно).")
add('')
for sec, title in (('expect', 'Ожидания (PREREG §6; исход — по вердиктам выше)'), ('main_question', 'Для главного вопроса'), ('next', 'Что дальше')):
    if NOTES.get(sec):
        add(f'## {title}')
        add('')
        for s_ in NOTES[sec]:
            add(f'- {s_}')
        add('')
if fc:
    add('## Вес опоры (PREREG §10)')
    add('')
    for k in ('P0', 'P1', 'P2', 'P3'):
        w, fl = fc['weights'][k], fc['false_level'][k]
        add(f"- {k}: {w['verdict']}; вес {n(w['bits'], 2, False)} бит; ложный уровень {n(fl['value'], 4, False)} ({fl['side']})"
            + (f"; описательная проверка по группам даёт {n(fl['groups_descr'], 4, False)} — больше" if fl.get('groups_larger') else '') + '.')
    add('- N и Т — 0 бит: служебное условие для P3 и проверка метода.')
    add('')
add('## Отклонения')
add('')
add('См. `DEVIATIONS.md`.' if os.path.exists(os.path.join(X, 'DEVIATIONS.md')) else 'Нет.')
open(OUT, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('записано', OUT, len(L), 'строк')
