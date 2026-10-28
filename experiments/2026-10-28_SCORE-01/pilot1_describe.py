#!/usr/bin/env python3
"""SCORE-01, микропилот 1 (формат «в лучшей половине»): описательная сводка по evals/<stage>.json.
Ничего не решает и не регистрирует — материал для выбора устройства основного прогона (PILOT1.md).
  python3 pilot1_describe.py pilot1_opus [pilot1_haiku ...]"""
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def mean(x):
    return sum(x) / len(x)


def sd(x):
    m = mean(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))


def boot_ci(x, n=10000, seed=1):
    rng = random.Random(seed)
    ms = sorted(mean([x[rng.randrange(len(x))] for _ in x]) for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n) - 1]


def pearson(a, b):
    ma, mb = mean(a), mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    return num / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))


def z_power(effect, sd_, n, z_a=1.959964):
    """Мощность двустороннего z-теста парной разности при истинном сдвиге effect (нормальное приближение)."""
    se = sd_ / math.sqrt(n)
    phi = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))
    return phi(effect / se - z_a) + phi(-effect / se - z_a)


def describe(stage):
    E = json.load(open(os.path.join(HERE, 'evals', f'{stage}.json')))
    rows = [r for r in E['rows'].values() if r['valid']]
    print(f'## {stage}: годных {len(rows)} из {len(E["rows"])}')
    by = {}
    for r in rows:
        by.setdefault(r['arm'], {})[r['task']] = r
    for arm, d in sorted(by.items()):
        ps = [x for r in d.values() for x in r['p']]
        hist = [0] * 10
        for x in ps:
            hist[min(int(x * 10), 9)] += 1
        ext = sum(1 for x in ps if x <= 0.1 or x >= 0.9)
        half = sum(1 for x in ps if x == 0.5)
        aucs = [r['auc'] for r in d.values()]
        # «четвёрка по рангу»: 4 наибольших p (ничьи — по номеру) против истинной четвёрки
        top4 = []
        for r in d.values():
            o = sorted(range(8), key=lambda i: (-r['p'][i], i))[:4]
            top4.append(sum(r['labels'][i] for i in o) / 4)
        sums = [r['sum_p'] for r in d.values()]
        print(f'{arm}: гистограмма p по десятым {hist}; крайних (≤0,1 или ≥0,9) {ext} из {len(ps)}; ровно 0,5 — {half}')
        print(f'   AUC по задачам: среднее {mean(aucs):.3f}, SD {sd(aucs):.3f}, ДИ95 бутстреп [{boot_ci(aucs)[0]:.3f}; {boot_ci(aucs)[1]:.3f}]; '
              f'задач с AUC > 0,5 — {sum(a > 0.5 for a in aucs)}, = 0,5 — {sum(a == 0.5 for a in aucs)}')
        print(f'   четвёрка по рангу: доля верных {mean(top4):.3f} [{boot_ci(top4)[0]:.3f}; {boot_ci(top4)[1]:.3f}] (случайно 0,5)')
        print(f'   сумма p: среднее {mean(sums):.2f}, мин {min(sums):.2f}, макс {max(sums):.2f}')
        # калибровка по корзинам уверенности
        bins = {}
        for r in d.values():
            for x, l in zip(r['p'], r['labels']):
                c = max(x, 1 - x)
                a = 0.5 if x == 0.5 else float((x > 0.5) == bool(l))
                bins.setdefault(min(int((c - 0.5) * 10), 4), []).append((c, a))
        print('   корзины уверенности (уверенность → точность, n): ' + '; '.join(
            f'{mean([c for c, _ in b]):.2f} → {mean([a for _, a in b]):.2f} ({len(b)})' for k, b in sorted(bins.items())))
    if {'LOG', 'WIN'} <= set(by):
        tasks = sorted(set(by['LOG']) & set(by['WIN']))
        pl = [x for t in tasks for x in by['LOG'][t]['p']]
        pw = [x for t in tasks for x in by['WIN'][t]['p']]
        side = sum(1 for a, b in zip(pl, pw) if (a > 0.5) == (b > 0.5) and a != 0.5 and b != 0.5)
        print(f'LOG против WIN на тех же кандидатах: корреляция p {pearson(pl, pw):.3f}; одна сторона от 0,5 — {side} из {len(pl)}')
        print('Парные разности WIN − LOG по задачам (среднее, ДИ95 бутстреп, SD; мощность при n = 100 для сдвигов 0,02/0,05):')
        for k in ('conf', 'acc', 'self_dec', 'logloss', 'brier', 'auc'):
            if k == 'self_dec':
                d_ = [(by['WIN'][t]['conf'] - by['WIN'][t]['acc']) - (by['LOG'][t]['conf'] - by['LOG'][t]['acc']) for t in tasks]
            elif k == 'auc':
                d_ = [by['WIN'][t]['auc'] - by['LOG'][t]['auc'] for t in tasks if not (math.isnan(by['WIN'][t]['auc']) or math.isnan(by['LOG'][t]['auc']))]
            else:
                d_ = [by['WIN'][t][k] - by['LOG'][t][k] for t in tasks]
            lo, hi = boot_ci(d_)
            s = sd(d_)
            print(f'   {k}: {mean(d_):+.4f} [{lo:+.4f}; {hi:+.4f}], SD {s:.4f}, n {len(d_)}; '
                  f'мощность n=100: 0,02 → {z_power(0.02, s, 100):.2f}, 0,05 → {z_power(0.05, s, 100):.2f}')
    print()


if __name__ == '__main__':
    for st in sys.argv[1:]:
        describe(st)
