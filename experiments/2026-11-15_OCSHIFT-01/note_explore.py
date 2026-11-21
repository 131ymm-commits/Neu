#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка записки EXPLORE-three-shifts.md: текст — мой, числа — из gha_out/ocshift_explore/explore_shifts.json
(прогон GitHub Actions) тем же форматированием, каким их сверяет ledger.py audit. python3 note_explore.py"""
import json
import os

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
d = json.load(open(os.path.join(ROOT, 'gha_out', 'ocshift_explore', 'explore_shifts.json'), encoding='utf-8'))
SH = d['shifts']
NAMES = {'OCCOR-01': 'OCCOR-01, a ∈ [100, 199]', 'OCMIX-01': 'OCMIX-01, a ∈ [200, 299]', 'OCREP-01': 'OCREP-01, a ∈ [300, 399]'}


def n(x, k=3, sign=False):
    s = f'{abs(x):.{k}f}'.replace('.', ',')
    if x < 0 and float(s.replace(',', '.')) != 0:
        return '−' + s
    return ('+' if sign and x > 0 else '') + s


def ci(v):
    return f"[{n(v['ci99'][0], 3, True)}; {n(v['ci99'][1], 3, True)}]"


L = []
a = L.append
a('# OCSHIFT-01 — разбор трёх готовых сдвигов (пост-хок, 15.11.2026)')
a('')
a('**Что это.** Разбор готовых ответов OCCOR-01, OCMIX-01 и OCREP-01 (те же 9 голов Pythia, сложение, три диапазона). Считал GitHub Actions (`gha_jobs/ocshift_explore.sh` → `gha_out/ocshift_explore/`, 3 мин 42 с; слово автора 15.11.2026 — все прогоны на сторонних площадках). Код — `explore_shifts.py`.')
a('')
a('**Статус.** Пост-хок: вердиктов прежних опытов не меняет, опорой не считается. Это основание гипотез и мощности OCSHIFT-01. Каждое число — из `explore_shifts.json`.')
a('')
a('## Главное')
a('- **База, которой не было ни в одном опыте линии:** одна лучшая голова (ONE-BEST) — голова с наибольшей точностью на ID; заявка — её собственная откалиброванная уверенность; между головами ничего не выбирается.')
a('- **На всех трёх сдвигах, в обеих частях (тест и пилот), ИОИ у ONE-BEST ниже, чем у лучшего из восьми оценщиков толпы.** По Брайеру выбранной заявки она лучше или вровень.')
a('')
a('| сдвиг, часть | ONE-BEST: T / C / ИОИ | лучший из восьми: кто, ИОИ | LR-AGREE | CONF | оракул | Брайер: ONE-BEST / лучший из восьми |')
a('|---|---|---|---|---|---|---|')
for s, parts in SH.items():
    for part in ('test', 'pilot'):
        r = parts[part]; e = r['evaluators']; ob = e['CONF']['one_best']
        best = min(e, key=lambda x: e[x]['ood']['ioi']); bb = min(e, key=lambda x: e[x]['ood']['brier'])
        a(f"| {NAMES[s]}, {'тест' if part == 'test' else 'пилот'} | {n(ob['T'])} / {n(ob['C'])} / {n(ob['ioi'])} | {best}, {n(e[best]['ood']['ioi'])} | "
          f"{n(e['LR-AGREE']['ood']['ioi'])} | {n(e['CONF']['ood']['ioi'])} | {n(r['oracle']['ood'])} | {n(ob['brier'])} / {n(e[bb]['ood']['brier'])} |")
a('')
a('- ONE-BEST во всех шести наборах — pythia-2.8b-deduped; она же лучшая по точности вне диапазона.')
a('- Оракул — доля задач OOD, где верна хотя бы одна голова. Запас до него большой, но ни один оценщик его не берёт.')
a('- Разности ИОИ, ДИ 99 % (вложенный бутстреп, 400 повторов; лучшая голова в каждом повторе выбирается заново):')
for s, parts in SH.items():
    b = parts['test']['boot']['diffs']; bp = parts['pilot']['boot']['diffs']
    a(f"  - {NAMES[s]}: ONE-BEST − LR-AGREE — тест {ci(b['ONE-BEST − LR-AGREE'])}, пилот {ci(bp['ONE-BEST − LR-AGREE'])}; ONE-BEST − CONF — тест {ci(b['ONE-BEST − CONF'])}, пилот {ci(bp['ONE-BEST − CONF'])}.")
a('')
a('## Почему толпа проигрывает (по числам; причины не проверялись)')
a('- **Выбор между головами не точнее лучшей головы.** T оценщиков толпы и точность ONE-BEST вне диапазона (тест):')
for s, parts in SH.items():
    r = parts['test']; e = r['evaluators']
    a(f"  - {NAMES[s]}: T оценщиков — от {n(min(v['ood']['T'] for v in e.values()))} до {n(max(v['ood']['T'] for v in e.values()))}; ONE-BEST — {n(r['one_best']['acc_ood'])}.")
r1 = SH['OCCOR-01']['test']['evaluators']
a(f"- **Где выбор отходит от ответа ONE-BEST, он чаще ошибается.** OCCOR-01, тест: LR-AGREE отходит в {n(r1['LR-AGREE']['vs_one_best']['switch'])} задач; там выбранный ответ верен в {n(r1['LR-AGREE']['vs_one_best']['T_selected_on_switch'])}, а ONE-BEST — в {n(r1['LR-AGREE']['vs_one_best']['T_one_best_on_switch'])}. У CONF — {n(r1['CONF']['vs_one_best']['switch'])}, {n(r1['CONF']['vs_one_best']['T_selected_on_switch'])} и {n(r1['CONF']['vs_one_best']['T_one_best_on_switch'])}.")
acc = SH['OCCOR-01']['test']['accuracy']
a(f"  - На этом сдвиге головы ломаются по-разному: pythia-6.9b — {n(acc['pythia-6.9b']['id'])} на ID и {n(acc['pythia-6.9b']['ood'])} вне диапазона; pythia-2.8b-deduped — {n(acc['pythia-2.8b-deduped']['id'])} и {n(acc['pythia-2.8b-deduped']['ood'])}.")
a('- **Отбор сам даёт самообман, без всякого сдвига («проклятие победителя»).** Самообман C − T на ID с кросс-подгонкой (5 частей: оценщик и калибровка — без части, выбор — на части) и на OOD, тест:')
a('')
a('| сдвиг | CONF: ID / OOD | VETO: ID / OOD | AGREE: ID / OOD | LR-AGREE: ID / OOD |')
a('|---|---|---|---|---|')
for s, parts in SH.items():
    e = parts['test']['evaluators']
    a(f"| {NAMES[s]} | " + ' | '.join(f"{n(e[x]['id_crossfit']['dec'], 3, True)} / {n(e[x]['ood']['dec'], 3, True)}" for x in ('CONF', 'VETO', 'AGREE', 'LR-AGREE')) + ' |')
a('')
a('- У ONE-BEST отбора нет. Её самообман вне диапазона (тест): ' + '; '.join(f"{NAMES[s].split(',')[0]} — {n(parts['test']['evaluators']['CONF']['one_best']['dec'], 3, True)}" for s, parts in SH.items()) + '.')
a('')
a('## Что ещё видно (описательно; в правила OCSHIFT-01 не идёт)')
a('- **Вторая калибровка после отбора (POST):** изотоника «заявка выбранного ответа → его правильность» по ID. Выбор не меняется, заявка падает. ИОИ, тест (было → стало, POST по кросс-подгонке):')
for s, parts in SH.items():
    e = parts['test']['evaluators']
    a(f"  - {NAMES[s]}: " + '; '.join(f"{x} {n(e[x]['ood']['ioi'])} → {n(e[x]['post_cv']['ioi'])}" for x in ('CONF', 'VETO', 'LR-AGREE')) + '.')
a('- **Слияние FUSE-MIN** (заявка головы — меньшая из заявок CONF и LR-AGREE, выбор — по ней). ИОИ / самообман, тест: ' + '; '.join(f"{NAMES[s].split(',')[0]} — {n(parts['test']['fusions']['FUSE-MIN']['ood']['ioi'])} / {n(parts['test']['fusions']['FUSE-MIN']['ood']['dec'], 3, True)}" for s, parts in SH.items()) + '. Лучше ONE-BEST на двух сдвигах, хуже на первом.')
a('- **Правило «самый скромный оценщик» (MIN-C)** — без правды взять того из пары CONF и LR-AGREE, у кого средняя заявка выбранных ответов ниже: ' + '; '.join(f"{NAMES[s].split(',')[0]} — {parts['test']['meta']['pair']['min_C']} (лучший в паре по ИОИ — {parts['test']['meta']['pair']['best_ioi']})" for s, parts in SH.items()) + '. По ИОИ это отчасти следует из самой меры: ИОИ не штрафует заниженную заявку.')
a('- **Согласованность заявок** (сумма заявок по разным ответам задачи не больше 1) как сигнал без правды не сработала: наименьший избыток на всех трёх сдвигах у LR-AGREE, в том числе там, где он хуже CONF.')
a('- **Сдвиг матрицы попарных совпадений ID → OOD** (средний модуль): ' + '; '.join(f"{NAMES[s].split(',')[0]} — {n(parts['test']['agree_shift']['mean_abs'])}" for s, parts in SH.items()) + '. Три точки; вывода нет.')
a('')
a('## Ограничения')
a('- Пост-хок на трёх сдвигах с одной подсказкой у каждого; головы и код одни и те же.')
a('- В разборе сравнивалось много вариантов (POST, слияния, согласованность, MIN-C). ONE-BEST — база, выведенная до чисел из наблюдения «T оценщиков ≈ точность лучшей головы» (отчёты OCREP-01 и OCMIX-01), но проверена она здесь же. Нужна проверка на свежих данных — это OCSHIFT-01.')
a('- ИОИ не штрафует заниженную заявку; поэтому рядом дан Брайер.')
open(os.path.join(X, 'EXPLORE-three-shifts.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\n'.join(L))
