#!/usr/bin/env python3
"""SCORE-01: таблицы микропилота 3 (чистый контекст) из evals/pilot3_<модель>.json — для PILOT3.md и §3 PREREG (числа — командой).
  python3 pilot3_tables.py opus haiku"""
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
f = lambda x, d=3: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
ARMS = ('LOG', 'WIN', 'NONE')


def mean(x):
    return sum(x) / len(x)


def boot(x, n=10000, seed=7):
    rng = random.Random(seed)
    ms = sorted(mean([x[rng.randrange(len(x))] for _ in x]) for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n) - 1]


def corr(a, b):
    ma, mb = mean(a), mean(b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))


def val(r, m):
    return r['conf'] - r['acc'] if m == 'self_dec' else (float(r['out']) if m == 'out' else r[m])


def load(model):
    E = json.load(open(os.path.join(HERE, 'evals', f'pilot3_{model}.json')))
    return E['rows'], sorted({v['task'] for v in E['rows'].values()})


def cell(rows, t, a, k):
    r = rows.get(f'{t}|{a}|{k}')
    return r if r and r['valid'] else None


def diff(rows, tasks, hi, lo, m, reps):
    """Разность рук hi − lo по задачам: величина руки — среднее по повторам reps (только задачи, где у обеих рук есть все повторы)."""
    out = []
    for t in tasks:
        a = [cell(rows, t, lo, k) for k in reps]; b = [cell(rows, t, hi, k) for k in reps]
        if all(a) and all(b) and not (m == 'auc' and any(math.isnan(r['auc']) for r in a + b)):
            out.append(mean([val(r, m) for r in b]) - mean([val(r, m) for r in a]))
    return out


def aa(rows, tasks, arm, m):
    out = []
    for t in tasks:
        r0, r1 = cell(rows, t, arm, '0'), cell(rows, t, arm, '1')
        if r0 and r1 and not (m == 'auc' and (math.isnan(r0['auc']) or math.isnan(r1['auc']))):
            out.append(val(r1, m) - val(r0, m))
    return out


def ci_txt(x, d=3):
    lo, hi = boot(x)
    return f'{f(mean(x), d)} [{f(lo, d)}; {f(hi, d)}]'


models = sys.argv[1:]
print('| Модель | Клетка | Годных | Точность | Уверенность | Самообман | AUC | Брайер | Выход, ток. |')
print('|---|---|---|---|---|---|---|---|---|')
for mdl in models:
    rows, tasks = load(mdl)
    for a in ARMS:
        for k in '01':
            v = [rows.get(f'{t}|{a}|{k}') for t in tasks]
            g = [r for r in v if r and r['valid']]
            au = [r['auc'] for r in g if not math.isnan(r['auc'])]
            print(f"| {mdl} | {a}, повтор {k} | {len(g)} из {len(v)} | {f(mean([r['acc'] for r in g]))} | {f(mean([r['conf'] for r in g]))} | "
                  f"{f(mean([val(r, 'self_dec') for r in g]))} | {f(mean(au))} | {f(mean([r['brier'] for r in g]))} | {mean([r['out'] for r in g]):.0f} |")
print()
print('| Модель | Пара вызовов | Корреляция p | Одна сторона от 0,5 |')
print('|---|---|---|---|')
for mdl in models:
    rows, tasks = load(mdl)
    pairs = [((a, '0'), (a, '1')) for a in ARMS] + [(('LOG', k), ('WIN', k)) for k in '01'] + [(('NONE', k), (o, k)) for o in ('LOG', 'WIN') for k in '01']
    for (a, ka), (b, kb) in pairs:
        pa, pb = [], []
        for t in tasks:
            ra, rb = cell(rows, t, a, ka), cell(rows, t, b, kb)
            if ra and rb:
                pa += ra['p']; pb += rb['p']
        side = sum(1 for x, y in zip(pa, pb) if (x > 0.5) == (y > 0.5) and x != 0.5 and y != 0.5)
        print(f'| {mdl} | {a}, повтор {ka} и {b}, повтор {kb} | {f(corr(pa, pb))} | {side} из {len(pa)} |')
print()
print('| Модель | Разность по задачам (95 % бутстреп) | Самообман | Точность | Уверенность | Брайер | Выход, ток. |')
print('|---|---|---|---|---|---|---|')
for mdl in models:
    rows, tasks = load(mdl)
    lines = []
    for a in ARMS:
        lines.append((f'A/A: {a}, повтор 1 − повтор 0', lambda m, a=a: aa(rows, tasks, a, m)))
    for k in '01':
        lines.append((f'WIN − LOG, повтор {k}', lambda m, k=k: diff(rows, tasks, 'WIN', 'LOG', m, (k,))))
    lines.append(('WIN − LOG, среднее двух повторов', lambda m: diff(rows, tasks, 'WIN', 'LOG', m, ('0', '1'))))
    for o in ('LOG', 'WIN'):
        lines.append((f'NONE − {o}, среднее двух повторов', lambda m, o=o: diff(rows, tasks, 'NONE', o, m, ('0', '1'))))
    for name, fn in lines:
        cells = [ci_txt(fn(m), 0 if m == 'out' else 3) for m in ('self_dec', 'acc', 'conf', 'brier', 'out')]
        print(f"| {mdl} | {name} (n = {len(fn('acc'))}) | " + ' | '.join(cells) + ' |')
