#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-03: каркас отчёта — написан до вывода анализа теста (проверен на заглушке). Все числа — из analysis.json анализа и из
разбора пилота; тексты выводов (заметки после данных) — отдельным файлом notes, если он задан. Вердикты и чтение — по PREREG.
  python3 report_ocdiv3.py ANALYSIS.json PILOT_N2.json OUT.md [--notes NOTES.json] [--commits K=V ...]"""
import json
import sys

RULES = ('П1', 'П2', 'П3')
RULE_TEXT = {'П1': 'Т4 = F − F₀(N0): ложное большинство сверх перестановочного нуля (повтор C-105)',
             'П2': 'Т4ᵈ = F − F₀(Nd): то же сверх нуля со стратами по трудности из входа (S = 8)',
             'П3': 'Т4-ID: та же F − F₀(N0) на задачах ID (контроль неспецифичности)'}
EXPECT = (('E1', 'П1 подтверждено (Т4 > 0; предохранитель держится)', 0.804),
          ('E2', 'П1 подтверждено с пометкой «общий»', 0.801),
          ('E3', 'П1 опровергнуто (Т4 < 0)', 0.0004),
          ('E4', 'П2 подтверждено (Т4ᵈ > 0; предохранитель держится)', 0.950),
          ('E5', 'П2 подтверждено с пометкой «общий»', 0.935),
          ('E6', 'П3 подтверждено (Т4-ID > 0)', 0.950),
          ('E7', 'опыт определён (тривиальное — вне сводной калибровки)', 0.950))


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


def outcomes(A):
    v = A['verdicts']
    m = A['marks']
    return {'E1': v['П1'] == 'подтверждено', 'E2': v['П1'] == 'подтверждено' and m['П1'] == 'общий', 'E3': v['П1'] == 'опровергнуто',
            'E4': v['П2'] == 'подтверждено', 'E5': v['П2'] == 'подтверждено' and m['П2'] == 'общий', 'E6': v['П3'] == 'подтверждено',
            'E7': bool(A['method']['ok'])}


def render(A, Pn, notes=None, commits=None):
    commits = commits or {}
    L = ['# OCDIV-03 «тысячи» — отчёт', '']
    L += [f"Предрегистрация — `PREREG-OCDIV-03.md`, коммит {commits.get('prereg', '⟨регистрация⟩')}; запуск — {commits.get('launch', '⟨запуск⟩')}; "
          f"анализ — {commits.get('analysis', '⟨анализ⟩')} (`gha_out/ocdiv3_sum_test/analysis.json`). Уровень {g(A['level'])} на сторону, M4: z = {g(A['z'], 3)}; "
          f"B = {A['B']}, описательные нули — {A['B_descr']}.", '']
    L += ['## Коротко', '']
    for k in RULES:
        e = A[k]
        mark = f" ({e['mark']})" if e.get('mark') else ''
        L.append(f"- **{k} — {e['verdict']}{mark}.** {RULE_TEXT[k]}: {f(e.get('delta'))}, M4 {ci(e)}.")
    rd = A['П2'].get('reading')
    if rd:
        L.append(f"- **Чтение П2 (Н1, совет 70):** {rd['reading']} — шаг 1 пройден в {rd['n_pass']} средах из {rd['n_valid']} годных.")
    L.append(f"- Опыт определён: {'да' if A['method']['ok'] else 'нет'} — годных сред {A['method']['n_valid']} из {A['method']['n_envs']}; "
             f"толпа {len(A['crowd_effective'])} из {len(A['crowd'])}, выбыли: {A['crowd_dropped'] or 'нет'}.")
    L += ['', '## Правила', '', '| Правило | Δ | M4 при 0,0025 | z\\* | вердикт по M4 | предохранитель | сред с интервалом > 0 (0,0025/5) | вердикт |',
          '|---|---|---|---|---|---|---|---|']
    for k in RULES:
        e = A[k]
        loo = e.get('leave_one_env_out', {})
        L.append(f"| {k} | {f(e.get('delta'))} | {ci(e)} | {g(e.get('z_star'), 1)} | {e.get('verdict_rule', '—') if e.get('verdict_rule') != 'не решено (предохранитель)' else 'см. предохранитель'} | "
                 f"{'держится' if loo.get('holds') else 'не держится'} | {e.get('n_env_positive', '—')} | {e['verdict']}{' (' + e['mark'] + ')' if e.get('mark') else ''} |")
    L += ['', '**Выборки «без одной среды»** (среднее четырёх, M4 при 0,0025):', '']
    L += ['| Правило | ' + ' | '.join(f'без {n}' for n in A['method']['valid']) + ' |', '|---|' + '---|' * len(A['method']['valid'])]
    for k in RULES:
        by = A[k].get('leave_one_env_out', {}).get('by_env', {})
        L.append(f'| {k} | ' + ' | '.join(f"{f(by[n]['delta'])} {ci(by[n])}" if n in by else '—' for n in A['method']['valid']) + ' |')
    L += ['', '## По средам (точки; в скобках — ст. откл. повторов)', '',
          '| Среда | толпа | вне диапазона / ID | оракул | F | Т4 | Т4ᵈ | Т4-ID |', '|---|---|---|---|---|---|---|---|']
    for n in A['method']['valid']:
        e = A['envs'][n]
        L.append(f"| {n} | {len(e['crowd'])} | {e['n_ood']} / {e['n_id']} | {g(e['oracle_ood'])} | {g(e['T4']['F'])} | {f(e['T4']['point'])} ({g(e['T4']['sd'])}) | "
                 f"{f(e['T4d']['point'])} ({g(e['T4d']['sd'])}) | {f(e['T4id']['point'])} ({g(e['T4id']['sd'])}) |")
    L += ['', '## Чтение П2: различают ли страты трудность на тесте (Н1)', '',
          '| Среда | пустых страт | ложное большинство: нижняя страта | верхняя | разность | M4 при 0,0025 | шаг 1 |', '|---|---|---|---|---|---|---|']
    for n in A['method']['valid']:
        r = A['envs'][n]['read']
        L.append(f"| {n} | {r['n_empty']} | {g(r['fm_bottom'])} | {g(r['fm_top'])} | {f(r['diff'])} | {ci(r)} | {'да' if r['step1'] else 'нет'} |")
    L += ['', '## Описательно (задано в PREREG; вердикт не меняет; M4 при 0,005)', '']
    dk = [('descr_descr трудность по входу', 'Т4 − Т4ᵈ: трудность по входу, F₀(Nd8) − F₀(N0)'),
          ('descr_descr совместность ошибок', 'совместность ошибок сверх неё, F₀(N3) − F₀(Nd8)'),
          ('descr_descr совпадение ответов', 'совпадение самих неверных ответов, F − F₀(N3)'),
          ('descr_T4 − T4-ID', 'Т4 − Т4-ID'),
          ('descr_T4 (страты по переносам)', 'Т4 со стратами по переносам (как в OCDIV-02)'),
          ('descr_descr T4 Nd2', 'Т4ᵈ при S = 2'), ('descr_descr T4 Nd4', 'Т4ᵈ при S = 4'), ('descr_descr T4 Nd16', 'Т4ᵈ при S = 16'),
          ('descr_descr T4 клетки c1×u', 'Т4 со стратами-клетками «c1 × u»')]
    L += ['| Величина | Δ | M4 при 0,005 |', '|---|---|---|']
    for key, txt in dk:
        e = A.get(key)
        if e:
            L.append(f"| {txt} | {f(e.get('delta'))} | {ci(e)} |")
    L += ['', '**Различение страт на тесте** (по правде теста):', '', '| Среда | AUC d̂ → ложное большинство | средний AUC моделей голов | наклон ложного большинства по стратам | размах d̂ |',
          '|---|---|---|---|---|']
    for n in A['method']['valid']:
        s = A['envs'][n]['separation']
        L.append(f"| {n} | {g(s['auc_dhat_false_major'])} | {g(s['auc_heads_mean'])} | {f(s['slope_false_major'])} | {g(s['dhat_range'])} |")
    L += ['', '**Т4 из формул** (DISTILL-01, ступень 1: условная независимость, неверные ответы без совпадений):', '',
          '| Среда | предсказано до прогона (толпа пилота) | по толпе теста | Т4 наблюдённый | Т4 − Т4ᵈ |', '|---|---|---|---|---|']
    pre = A.get('formula_pilot_prediction') or {}
    for n in A['method']['valid']:
        fm = A['formula'][n]
        L.append(f"| {n} | {f(pre.get(n, {}).get('T4_pred'))} | {f(fm['T4_pred'])} | {f(fm['T4_observed'])} | {f(fm['T4_minus_T4d'])} |")
    hm = A.get('homoplasy_mean') or {}
    L += ['', f"- Гомоплазия (среднее сред): H {g(hm.get('H'))}, H₀ {g(hm.get('H0'))}, H − H₀ {f(hm.get('diff'))}."]
    pa = A.get('pairs') or {}
    if pa:
        L.append(f"- Пары производителей: контраст «одного − разных» {f(pa.get('observed'))}, точное p = {g(pa.get('p_exact'))} (перебор {pa.get('n_structures')} структур; "
                 'наименьшее возможное p = 1/105).')
    rc = A.get('repeat_check') or []
    if rc:
        L.append('- ДЕТЕРМИНИЗМ-НА-3: ' + '; '.join(f"{x['model']} на {x['env']} — ответы совпали в доле {g(x['answers_equal'])}, наибольшая разность logp "
                                                    f"{g(x['max_abs_dlogp'], 6) if x['max_abs_dlogp'] is not None else '—'}" for x in rc) + '.')
    ex = sum(A['envs'][n]['extra_tokens']['n_cells'] for n in A['method']['valid'])
    L.append(f"- Прибор: числовых ответов толпы с лишними токенами — {ex}" + (' (пересчёт — в analysis.json, поле extra_tokens.recount).' if ex else '.'))
    L.append(f"- Версии анализа: python {A['versions']['python']}, numpy {A['versions']['numpy']}, scipy {A['versions']['scipy']}.")
    L += ['', '## Ожидания (PREREG §6)', '', '| № | Исход | Вероятность | Сбылось |', '|---|---|---|---|']
    oc = outcomes(A)
    for i, t, p in EXPECT:
        L.append(f"| {i} | {t} | {g(p, 4 if p < 0.01 else 3)} | {'да' if oc[i] else 'нет'} |")
    L += ['', '## Вес опоры (PREREG §10)', '',
          '- Веса — верхняя оценка, не для `journal/support_bits.json`: перенос M4 на 0,0025 для среднего пяти сред не проверен.']
    pw = Pn['power']
    keyp = {'П1': 'П1 Т4', 'П2': 'П2 Т4ᵈ (S = 8)', 'П3': 'П3 Т4-ID'}
    import math
    for k in RULES:
        v = A[k]['verdict']
        pc = pw[keyp[k]]['power']['confirm']
        w = math.log2(pc / 0.0025) if v == 'подтверждено' else (-math.log2(pc / 0.0025) if v == 'опровергнуто' else 0.0)
        L.append(f"- {k}: {v} — {g(w, 2)} бита" + (f" (log₂({g(pc, 3)} / 0,0025))" if v in ('подтверждено', 'опровергнуто') else ''))
    if notes:
        L += ['', '## После данных (заметки; причина — только проверенная)', '']
        L += [f'- {x}' for x in notes.get('notes', [])]
    L += ['', '## Чего отчёт не утверждает', '',
          '- Что эффект есть у других семейств задач, подсказок и голов: пять сред «тысяч», одна подсказка (p = 3), семь малых открытых голов.',
          '- Причину ложного большинства: разложение и Т4 из формул — описательно.',
          '- Что уровень M4 точен для среднего пяти сред: перенос M4 на 0,0025 не проверен (номинальный уровень).']
    return '\n'.join(L) + '\n'


def main(a):
    A = json.load(open(a[0], encoding='utf-8'))
    Pn = json.load(open(a[1], encoding='utf-8'))
    notes = json.load(open(a[a.index('--notes') + 1], encoding='utf-8')) if '--notes' in a else None
    commits = dict(x.split('=', 1) for x in a[a.index('--commits') + 1:]) if '--commits' in a else {}
    open(a[2], 'w', encoding='utf-8').write(render(A, Pn, notes, commits))
    print('записано', a[2])


if __name__ == '__main__':
    main(sys.argv[1:])
