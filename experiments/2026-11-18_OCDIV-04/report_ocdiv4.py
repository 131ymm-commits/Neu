#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-04: каркас отчёта — написан до вывода анализа теста (проверен на заглушке). Все числа — из analysis.json и разбора пилота;
тексты выводов после данных — отдельным файлом notes (short, main_q, next, notes, council), если он задан. Вердикты — из json по PREREG.
  python3 report_ocdiv4.py ANALYSIS.json PILOT.json EXPECT.json OUT.md [--notes NOTES.json] [--commits K=V ...]"""
import json
import math
import sys

RULE_TEXT = {'Р1-Т': 'Δ3c = F − F₀(N3c) вне диапазона, «тысячи» (8 сред): совпадение самих неверных ответов при той же картине «кто где ошибся» и том же узоре переносов',
             'Р1-Л': 'то же на «длине» (3 среды; только часть А)',
             'Р2-Т': 'K вне диапазона минус K на ID, «тысячи»: совпадение смещения при совместной ошибке пары голов сверх N3c (специфичность для сдвига)'}
FAM_RU = {'thousands': '«тысячи»', 'length': '«длина»'}
DESCR_RU = {'d3c_id': 'Δ3c на ID', 'k_ood': 'K вне диапазона', 'k_id': 'K на ID', 't4_ood': 'Т4 = F − F₀(N0) вне диапазона',
            'd3u_ood': 'Δ3c со стратами-клетками «c1 × u»', 'd3c_diff': 'Δ3c вне диапазона минус на ID (мера скептика)'}


def f(x, d=4):
    if x is None or x != x:
        return '—'
    return f'{x:+.{d}f}'.replace('-', '−').replace('.', ',')


def g(x, d=4):
    if x is None or x != x:
        return '—'
    return f'{x:.{d}f}'.replace('.', ',')


def ci(e, d=4):
    return f"[{f(e['ci'][0], d)}; {f(e['ci'][1], d)}]" if e and 'ci' in e else '—'


def render(A, Pn, X, notes=None, commits=None):
    commits = commits or {}
    L = ['# OCDIV-04 «СОВПАДЕНИЕ-СМЕЩЕНИЙ» — отчёт', '']
    L += [f"Предрегистрация — `PREREG-OCDIV-04.md`, коммит {commits.get('prereg', '⟨регистрация⟩')}; запуск — {commits.get('launch', '⟨запуск⟩')}; "
          f"анализ — {commits.get('analysis', '⟨анализ⟩')} (`gha_out/ocdiv4_sum_test/analysis.json`). Уровень {g(A['level'])} на сторону, M4: "
          f"z = {g(A['z'], 3)}; B = {A['B']}; на точку — {A['K_point']} перестановок нуля, на повтор — {A['K_boot']}.", '']
    L += ['## Коротко', '']
    for r, e in A['rules'].items():
        act = '' if e.get('active', True) else ' (описательно: мощность по пилоту ниже 0,2)'
        sg = e.get('signs', {})
        signs = f"знак по средам: > 0 — {len(sg.get('pos', []))}, < 0 — {len(sg.get('neg', []))}, накрывает 0 — {len(sg.get('zero', []))}" if sg else ''
        tb = e.get('t_envs', {})
        L.append(f"- **{r} — {e['verdict_rule']}{act}.** {RULE_TEXT[r]}: {f(e.get('delta'))}, M4 {ci(e)}; t по средам {g(tb.get('t'), 2)} "
                 f"при пороге {g(tb.get('crit'), 3)} (df = {tb.get('df', '—')}); {signs}" + (f"; {e['mark']}" if e.get('mark') else '') + '.')
    for fam, F in A['families'].items():
        L.append(f"- {FAM_RU[fam]}: годных сред {len(F['valid'])} из {len(F['envs'])}, в правилах {len(F['use'])}; опыт по семейству "
                 f"{'определён' if F['method_ok'] else 'не определён'}; толпа {len(F['crowd_effective'])} из 7, выбыли: {F['crowd_dropped'] or 'нет'}.")
    if notes and notes.get('short'):
        L += [f'- {x}' for x in notes['short']]
    L += ['', '## Правила', '', '| Правило | Δ | M4 при 0,0025 | часть А | t по средам | порог t | знак по средам: > 0 / < 0 / накрывает 0 | вердикт |',
          '|---|---|---|---|---|---|---|---|']
    for r, e in A['rules'].items():
        sg, tb = e.get('signs', {}), e.get('t_envs', {})
        L.append(f"| {r} | {f(e.get('delta'))} | {ci(e)} | {e.get('verdict', '—')} | {g(tb.get('t'), 2)} | {g(tb.get('crit'), 3)} | "
                 f"{len(sg.get('pos', []))} / {len(sg.get('neg', []))} / {len(sg.get('zero', []))} | {e['verdict_rule']} |")
    L += ['', 'Часть А — нижняя граница M4 среднего сред > 0; часть Б — t по средам (среды как выборка) выше квантиля t(0,9975; n − 1). '
          'Интервал среды для знака — при 0,0025 / n. Р1-Л — только часть А (три среды).']
    for fam, F in A['families'].items():
        L += ['', f"## По средам: {FAM_RU[fam]} (точки; в скобках — ст. откл. повторов)", '',
              '| Среда | толпа | вне диапазона / ID | оракул | F вне диапазона | Δ3c вне диапазона | Δ3c на ID | K вне диапазона | K на ID | Т4 (N0) |',
              '|---|---|---|---|---|---|---|---|---|---|']
        for n, e in F['envs'].items():
            if not e.get('valid'):
                L.append(f"| {n} | {len(e['crowd'])} | {e['n_ood']} / {e['n_id']} | — | — | — | — | — | — | — |")
                continue
            L.append(f"| {n} | {len(e['crowd'])} | {e['n_ood']} / {e['n_id']} | {g(e['oracle_ood'])} | {g(e['d3c_ood']['F'])} | "
                     f"{f(e['d3c_ood']['point'])} ({g(e['d3c_ood']['sd'])}) | {f(e['d3c_id']['point'])} ({g(e['d3c_id']['sd'])}) | "
                     f"{f(e['k_ood']['point'])} ({g(e['k_ood']['sd'])}) | {f(e['k_id']['point'])} ({g(e['k_id']['sd'])}) | "
                     f"{f(e['t4_ood']['point'])} ({g(e['t4_ood']['sd'])}) |")
    L += ['', '## Описательно (задано в HYPOTHESIS и PREREG; вердикт не меняет; M4 при 0,005)', '',
          '| Семейство | Величина | Среднее | M4 при 0,005 | t по средам |', '|---|---|---|---|---|']
    for k, e in A['descr'].items():
        fam, key = k.split(' ', 1)
        if key not in DESCR_RU or 'ci' not in e:
            continue
        L.append(f"| {FAM_RU[fam]} | {DESCR_RU[key]} | {f(e['delta'])} | {ci(e)} | {g(e.get('t_envs', {}).get('t'), 2)} |")
    L += ['', '**Виды совпавших смещений вне диапазона** (доли среди совпавших пар; виды — по слагаемым и коду):', '']
    for fam, F in A['families'].items():
        for n, e in F['envs'].items():
            if e.get('valid'):
                kd = e['same_pairs_ood']['kinds']
                L.append(f"- {n}: " + ', '.join(f"{k} {g(v, 3)}" for k, v in list(kd.items())[:3]) + f" (совпавших пар {e['same_pairs_ood']['n']})")
    pa = A.get('pairs') or {}
    if pa:
        L += ['', f"- Пары производителей (ОТРИЦАТЕЛЬНЫЙ-КОНТРОЛЬ-ПАРЫ): контраст «одного − разных» {f(pa.get('observed'))}, точное p = {g(pa.get('p_exact'))} "
                  f"(перебор {pa.get('n_structures')} структур; наименьшее возможное p = 1/105)."]
    rc = A.get('repeat_check') or []
    if rc:
        L.append('- ДЕТЕРМИНИЗМ-НА-3: ' + '; '.join(f"{x['model']} на {x['env']} — ответы совпали в доле {g(x['answers_equal'])}, наибольшая разность logp "
                                                    f"{g(x['max_abs_dlogp'], 6) if x['max_abs_dlogp'] is not None else '—'}" for x in rc) + '.')
    ex = sum(e.get('extra_tokens', {}).get('n_cells', 0) for F in A['families'].values() for e in F['envs'].values() if e.get('valid'))
    L.append(f"- Прибор: числовых ответов толпы с лишними токенами — {ex}" + (' (пересчёт — в analysis.json, поле extra_tokens.recount).' if ex else '.'))
    L.append(f"- Версии анализа: python {A['versions']['python']}, numpy {A['versions']['numpy']}, scipy {A['versions']['scipy']}.")
    L += ['', '## Ожидания (PREREG §6)', '', '| № | Исход | Вероятность | Сбылось |', '|---|---|---|---|']
    for e in X['expectations']:
        got = e['outcome_of'](A) if callable(e.get('outcome_of')) else outcome(A, e['key'])
        L.append(f"| {e['id']} | {e['text']} | {g(e['p'], 4 if e['p'] < 0.01 else 3)} | {'да' if got else 'нет'} |")
    if notes:
        for key, title in (('main_q', 'Для главного вопроса'), ('next', 'Что дальше')):
            if notes.get(key):
                L += ['', f'## {title}', ''] + [f'- {x}' for x in notes[key]]
    L += ['', '## Вес опоры (PREREG §10)', '', '- Веса — верхняя оценка, не для `journal/support_bits.json`: перенос M4 на 0,0025 для среднего сред не проверен.']
    for r, e in A['rules'].items():
        pw = (Pn['power'].get(r) or {}).get('power', {})
        pc = pw.get('confirm')
        v = e['verdict_rule']
        w = math.log2(pc / 0.0025) if (pc and v in ('подтверждено', 'вне диапазона больше', 'вне диапазона меньше')) else (
            -math.log2(pc / 0.0025) if (pc and v == 'опровергнуто') else 0.0)
        L.append(f"- {r}: {v} — {g(w, 2)} бита" + (f" (log₂({g(pc, 3)} / 0,0025))" if w else ''))
    if notes and notes.get('notes'):
        L += ['', '## После данных (заметки; причина — только проверенная)', ''] + [f'- {x}' for x in notes['notes']]
    L += ['', '## Чего отчёт не утверждает', '',
          '- Что эффект есть у других задач, подсказок и голов: «тысячи» и «длина», одна подсказка (p = 3), семь малых открытых голов.',
          '- Причину совпадения неверных ответов на одних и тех же задачах: виды смещений — описательно.',
          '- Что уровень M4 точен для среднего сред: перенос M4 на 0,0025 не проверен (номинальный уровень).']
    if notes and notes.get('council'):
        L += ['', f"## {notes['council']['title']}", ''] + [f'- {x}' for x in notes['council']['items']]
    return '\n'.join(L) + '\n'


def outcome(A, key):
    """Исход ожидания по ключу (PREREG §6): «R:подтверждено» и т. п. — по вердикту правила; «method» — опыт определён по обоим семействам."""
    if key == 'method':
        return all(F['method_ok'] for F in A['families'].values())
    r, v = key.split(':', 1)
    return A['rules'][r]['verdict_rule'] == v


def main(a):
    A = json.load(open(a[0], encoding='utf-8'))
    Pn = json.load(open(a[1], encoding='utf-8'))
    X = json.load(open(a[2], encoding='utf-8'))
    notes = json.load(open(a[a.index('--notes') + 1], encoding='utf-8')) if '--notes' in a else None
    commits = dict(x.split('=', 1) for x in a[a.index('--commits') + 1:]) if '--commits' in a else {}
    open(a[3], 'w', encoding='utf-8').write(render(A, Pn, X, notes, commits))
    print('записано', a[3])


if __name__ == '__main__':
    main(sys.argv[1:])
