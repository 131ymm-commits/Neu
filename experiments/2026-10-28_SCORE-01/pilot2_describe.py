#!/usr/bin/env python3
"""SCORE-01, микропилот 2: повторы (A/A) и рука NONE. Описательно, ничего не регистрирует.
Вход — evals/<этап>.json, собранный score01.py metrics из выгрузок микропилотов 1 и 2 одной модели
(id «задача|рука|повтор»: LOG|0, WIN|0 — пилот 1; NONE|0, LOG|1, WIN|1 — пилот 2).
  python3 pilot2_describe.py pilot12_opus pilot12_haiku"""
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MEAS = ('conf', 'acc', 'self_dec', 'brier', 'logloss', 'auc', 'ioi')


def mean(x):
    return sum(x) / len(x)


def sd(x):
    m = mean(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))


def boot(x, n=10000, seed=7):
    rng = random.Random(seed)
    ms = sorted(mean([x[rng.randrange(len(x))] for _ in x]) for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n) - 1]


def corr(a, b):
    ma, mb = mean(a), mean(b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))


def val(r, m):
    return r['conf'] - r['acc'] if m == 'self_dec' else r[m]


def pairs(rows, tasks, hi, lo, m):
    out = []
    for t in tasks:
        a, b = rows.get(f'{t}|{lo}'), rows.get(f'{t}|{hi}')
        if a and b and a['valid'] and b['valid'] and not (m == 'auc' and (math.isnan(a['auc']) or math.isnan(b['auc']))):
            out.append(val(b, m) - val(a, m))
    return out


def line(name, x):
    lo, hi = boot(x)
    return f'{name}: {mean(x):+.4f} [{lo:+.4f}; {hi:+.4f}], SD {sd(x):.4f}, n {len(x)}'


def describe(st):
    E = json.load(open(os.path.join(HERE, 'evals', f'{st}.json')))
    rows = {'|'.join(k.split('|')[:2]) + ('' if k.endswith('|0') else '_' + k.split('|')[2]): v for k, v in E['rows'].items()}
    tasks = sorted({v['task'] for v in E['rows'].values()})
    cells = sorted({'|'.join(k.split('|')[1:]) for k in E['rows']})
    print(f'## {st}: задач {len(tasks)}, клетки {cells}, негодных {sum(1 for v in E["rows"].values() if not v["valid"])}')
    for c in ('LOG', 'LOG_1', 'WIN', 'WIN_1', 'NONE'):
        v = [rows.get(f'{t}|{c}') for t in tasks]
        v = [r for r in v if r and r['valid']]
        if v:
            print(f'  {c:6s}: ' + ', '.join(f'{m} {mean([val(r, m) for r in v if not (m == "auc" and math.isnan(r["auc"]))]):.3f}' for m in MEAS)
                  + f', выход {mean([r["out"] for r in v]):.0f} ток.')
    # согласие повторов: корреляция p одного промпта в двух вызовах против разных рук
    for a, b in (('LOG', 'LOG_1'), ('WIN', 'WIN_1'), ('LOG', 'WIN'), ('LOG_1', 'WIN_1'), ('NONE', 'LOG'), ('NONE', 'WIN')):
        pa, pb = [], []
        for t in tasks:
            ra, rb = rows.get(f'{t}|{a}'), rows.get(f'{t}|{b}')
            if ra and rb and ra['valid'] and rb['valid']:
                pa += ra['p']; pb += rb['p']
        if pa:
            side = sum(1 for x, y in zip(pa, pb) if (x > 0.5) == (y > 0.5) and x != 0.5 and y != 0.5)
            print(f'  согласие {a} и {b}: корреляция p {corr(pa, pb):.3f}, одна сторона {side} из {len(pa)}')
    print('  разности по задачам (среднее [95 % бутстреп], SD):')
    for m in MEAS:
        print(f'   {m}:')
        print('     ' + line('A/A LOG_1 − LOG', pairs(rows, tasks, 'LOG_1', 'LOG', m)))
        print('     ' + line('A/A WIN_1 − WIN', pairs(rows, tasks, 'WIN_1', 'WIN', m)))
        print('     ' + line('WIN − LOG (повтор 0)', pairs(rows, tasks, 'WIN', 'LOG', m)))
        print('     ' + line('WIN_1 − LOG_1 (повтор 1)', pairs(rows, tasks, 'WIN_1', 'LOG_1', m)))
        # среднее двух повторов на задачу
        two = []
        for t in tasks:
            ks = [f'{t}|{c}' for c in ('LOG', 'LOG_1', 'WIN', 'WIN_1')]
            if all(rows.get(k) and rows[k]['valid'] for k in ks) and not (m == 'auc' and any(math.isnan(rows[k]['auc']) for k in ks)):
                two.append((val(rows[ks[2]], m) + val(rows[ks[3]], m)) / 2 - (val(rows[ks[0]], m) + val(rows[ks[1]], m)) / 2)
        if two:
            print('     ' + line('WIN − LOG (среднее двух повторов)', two))
        # NONE шла в одном прогоне с повторами LOG_1 и WIN_1 (вперемешку по задачам) — главное сравнение с ними;
        # с LOG и WIN пилота 1 она смешана со временем вызова
        print('     ' + line('NONE − LOG_1 (один прогон)', pairs(rows, tasks, 'NONE', 'LOG_1', m)))
        print('     ' + line('WIN_1 − NONE (один прогон)', pairs(rows, tasks, 'WIN_1', 'NONE', m)))
        print('     ' + line('NONE − LOG (разные прогоны)', pairs(rows, tasks, 'NONE', 'LOG', m)))
        print('     ' + line('WIN − NONE (разные прогоны)', pairs(rows, tasks, 'WIN', 'NONE', m)))
    print('   выход, ток. (дрейф между прогонами пилота 1 и 2):')
    for hi, lo in (('LOG_1', 'LOG'), ('WIN_1', 'WIN'), ('WIN', 'LOG'), ('WIN_1', 'LOG_1'), ('NONE', 'LOG_1'), ('NONE', 'WIN_1')):
        print('     ' + line(f'{hi} − {lo}', pairs(rows, tasks, hi, lo, 'out')))
    print()


if __name__ == '__main__':
    for s in sys.argv[1:]:
        describe(s)
