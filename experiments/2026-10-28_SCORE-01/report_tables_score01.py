#!/usr/bin/env python3
"""SCORE-01: таблицы отчёта из analysis_score01.json (числа в отчёт — командой, не перепечаткой; округление — один раз, из
неокруглённых чисел анализа: урок TRUST-04, находка 6). Вердиктов не меняет. Записан до регистрации и до теста; проверен на
сухом прогоне (dry/analysis_dry*.json).
  python3 report_tables_score01.py [analysis_score01.json] > run/report_tables.md"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from analyze_score01 import PRED  # noqa: E402

R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'analysis_score01.json')))
f = lambda x, d=3: '—' if x is None else f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
STAGES = [s for s in ('main_opus', 'rep_opus', 'main_haiku', 'rep_haiku') if s in R['stages']]
P = {p['id']: p for p in PRED}

print('### Руки по этапам (средние по вызовам; `score01.py metrics`)\n')
print('| Этап | Рука | Годных | Точность | Уверенность | Самообман | Брайер | Лог-потеря | AUC (по всем) | ИОИ = незнание + самообман | Выход, ток. |')
print('|---|---|---|---|---|---|---|---|---|---|---|')
for st in STAGES:
    for arm, m in R['stages'][st]['summary'].items():
        print(f"| {st} | {arm} | {m['n'] - m['invalid']} из {m['n']} | {f(m['acc'])} | {f(m['conf'])} | {f(m['self_dec'])} | {f(m['brier'])} | "
              f"{f(m['logloss'])} | {f(m['auc_pooled'])} | {f(m['ioi'])} = {f(m['ignorance'])} + {f(m['deception'])} | {f(m['out'], 0)} |")

print('\n### Предсказания (основная выборка и повтор; эквивалентность — 90 % интервал, остальное — 95 %)\n')
print('| | Модель | Предсказание | Основная: среднее [интервал], n | Вердикт | Повтор: среднее [интервал], n | Вердикт |')
print('|---|---|---|---|---|---|---|')
for pid, p in P.items():
    cells = []
    for s in ('main', 'rep'):
        v = R['verdicts'].get(f"{pid}|{s}_{p['model']}")
        if v is None:
            cells += ['—', '—']; continue
        d = 0 if p['measure'] == 'out' else 3
        ci = v.get('ci90') if p['kind'] == 'equiv' else v.get('ci95')
        val = f"{f(v['mean'], d)} [{f(ci[0], d)}; {f(ci[1], d)}], {v['n']} из {v['n_tasks']}" if 'mean' in v else f"{v['n']} из {v['n_tasks']}"
        cells += [val, v['outcome'] + (f" (чтение: {v['reading']})" if 'reading' in v else '')]
    print(f"| {pid} | {p['model']} | {p['text']} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} |")

print('\n### Сводные и статус\n')
print('| Сводный | Основная: исход | Чтение | Повтор: исход | Чтение | Статус |')
print('|---|---|---|---|---|---|')
for c, s in R['status'].items():
    print(f"| {c} | {s['main']} | {s['main_reading']} | {s['rep'] or '—'} | {s['rep_reading'] or '—'} | {s['status']} |")

print('\n### Проверка контекста этапов (§2, §4)\n')
print('| Этап | Вызовов | Пропущено | Наибольший \\|остаток\\| | SD остатка | Доля \\|остаток\\| > порога | Наклон, ток./ч | Длительность, ч | Конфигурация | Флаг |')
print('|---|---|---|---|---|---|---|---|---|---|')
for st in STAGES:
    c = R['ctx'].get(st)
    if not c:
        print(f'| {st} | — | — | — | — | — | — | — | — | нет проверки |'); continue
    cfg = c.get('config') or {}
    print(f"| {st} | {c['n']} | {c['skipped']} | {f(c.get('max_abs_resid'), 1)} | {f(c.get('sd_resid'), 1)} | {f(c.get('frac_resid_gt'))} | "
          f"{f(c.get('slope_per_hour'), 2)} | {f(c.get('span_hours'), 2)} | {'чистая' if cfg.get('ok') else 'НЕ та'} | {'да' if c['flag'] else 'нет'} |")

if R.get('aa'):
    print('\n### Встроенный A/A у Haiku (повтор 1 − повтор 0, 90 % интервал; допуски SA)\n')
    print('| Этап | Рука и мера | Среднее [90 %] | n | Внутри допуска | Целиком вне |')
    print('|---|---|---|---|---|---|')
    for st, aa in R['aa'].items():
        for k, v in aa.items():
            if k.startswith('_'):
                continue
            print(f"| {st} | {k} (±{f(v['margin'], 2)}) | {f(v['mean'])} [{f(v['ci90'][0])}; {f(v['ci90'][1])}] | {v['n']} | "
                  f"{'да' if v['within'] else 'нет'} | {'да' if v['outside'] else 'нет'} |")

if R.get('coverage'):
    print('\n### Покрытие заданий\n')
    print('| Этап | Заданий | Записей | Нет записи | Негодных |')
    print('|---|---|---|---|---|')
    for st, c in R['coverage'].items():
        print(f"| {st} | {c['jobs']} | {c['rows']} | {c['missing']} | {c['invalid']} |")
