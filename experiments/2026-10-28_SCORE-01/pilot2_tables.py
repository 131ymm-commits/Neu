#!/usr/bin/env python3
"""SCORE-01: таблицы PILOT2.md из evals/pilot12_<модель>.json (числа — командой).
  python3 pilot2_tables.py opus haiku"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pilot2_describe import boot, corr, mean, pairs, sd, val  # noqa: E402

f = lambda x, d=3: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
CELLS = (('LOG', 'LOG, повтор 0 (пилот 1)'), ('WIN', 'WIN, повтор 0 (пилот 1)'), ('LOG_1', 'LOG, повтор 1 (пилот 2)'),
         ('WIN_1', 'WIN, повтор 1 (пилот 2)'), ('NONE', 'NONE, повтор 0 (пилот 2)'))


def load(model):
    E = json.load(open(os.path.join(HERE, 'evals', f'pilot12_{model}.json')))
    rows = {'|'.join(k.split('|')[:2]) + ('' if k.endswith('|0') else '_' + k.split('|')[2]): v for k, v in E['rows'].items()}
    return rows, sorted({v['task'] for v in E['rows'].values()}), E


print('| Модель | Клетка | Годных | Точность | Уверенность | Самообман | AUC | Брайер | Выход, ток. |')
print('|---|---|---|---|---|---|---|---|---|')
for m in sys.argv[1:]:
    rows, tasks, E = load(m)
    for c, name in CELLS:
        v = [rows[f'{t}|{c}'] for t in tasks if f'{t}|{c}' in rows]
        g = [r for r in v if r['valid']]
        au = [r['auc'] for r in g if not math.isnan(r['auc'])]
        print(f"| {m} | {name} | {len(g)} из {len(v)} | {f(mean([r['acc'] for r in g]))} | {f(mean([r['conf'] for r in g]))} | "
              f"{f(mean([val(r, 'self_dec') for r in g]))} | {f(mean(au))} | {f(mean([r['brier'] for r in g]))} | {mean([r['out'] for r in g]):.0f} |")
print()
print('| Модель | Пара | Корреляция p | Одна сторона от 0,5 |')
print('|---|---|---|---|')
for m in sys.argv[1:]:
    rows, tasks, E = load(m)
    for a, b in (('LOG', 'LOG_1'), ('WIN', 'WIN_1'), ('LOG', 'WIN'), ('LOG_1', 'WIN_1'), ('NONE', 'LOG_1'), ('NONE', 'WIN_1')):
        pa, pb = [], []
        for t in tasks:
            ra, rb = rows.get(f'{t}|{a}'), rows.get(f'{t}|{b}')
            if ra and rb and ra['valid'] and rb['valid']:
                pa += ra['p']; pb += rb['p']
        side = sum(1 for x, y in zip(pa, pb) if (x > 0.5) == (y > 0.5) and x != 0.5 and y != 0.5)
        nm = lambda c: c.replace('_1', ', повтор 1') if c.endswith('_1') else c + ', повтор 0'
        print(f'| {m} | {nm(a)} и {nm(b)} | {f(corr(pa, pb))} | {side} из {len(pa)} |')
print()
print('| Модель | Разность по задачам | Самообман | Точность | Уверенность | Выход, ток. |')
print('|---|---|---|---|---|---|')
for m in sys.argv[1:]:
    rows, tasks, E = load(m)
    for hi, lo, name in (('LOG_1', 'LOG', 'A/A: LOG, повтор 1 − повтор 0'), ('WIN_1', 'WIN', 'A/A: WIN, повтор 1 − повтор 0'),
                         ('WIN', 'LOG', 'WIN − LOG, пилот 1'), ('WIN_1', 'LOG_1', 'WIN − LOG, пилот 2'),
                         ('NONE', 'LOG_1', 'NONE − LOG, пилот 2'), ('NONE', 'WIN_1', 'NONE − WIN, пилот 2')):
        cell = []
        for meas, d in (('self_dec', 3), ('acc', 3), ('conf', 3), ('out', 0)):
            x = pairs(rows, tasks, hi, lo, meas)
            lo_, hi_ = boot(x)
            cell.append(f'{f(mean(x), d)} [{f(lo_, d)}; {f(hi_, d)}]')
        print(f'| {m} | {name} (n = {len(pairs(rows, tasks, hi, lo, "acc"))}) | ' + ' | '.join(cell) + ' |')
    # среднее двух повторов
    two = {k: [] for k in ('self_dec', 'acc', 'conf', 'out')}
    for t in tasks:
        ks = [f'{t}|{c}' for c in ('LOG', 'LOG_1', 'WIN', 'WIN_1')]
        if all(rows.get(k) and rows[k]['valid'] for k in ks):
            for meas in two:
                two[meas].append((val(rows[ks[2]], meas) + val(rows[ks[3]], meas)) / 2 - (val(rows[ks[0]], meas) + val(rows[ks[1]], meas)) / 2)
    cell = []
    for meas, d in (('self_dec', 3), ('acc', 3), ('conf', 3), ('out', 0)):
        lo_, hi_ = boot(two[meas])
        cell.append(f'{f(mean(two[meas]), d)} [{f(lo_, d)}; {f(hi_, d)}]')
    print(f'| {m} | WIN − LOG, среднее двух повторов (n = {len(two["acc"])}) | ' + ' | '.join(cell) + ' |')
