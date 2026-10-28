#!/usr/bin/env python3
"""SCORE-01: мощность и ложный уровень предсказаний PREREG по пилотам (evals/pilot12_<модель>.json).
Предсказания — analyze_score01.PRED (одна копия). Разность одного вызова на задачу оценивается по парам пилота:
LOG|0–WIN|0 (пилот 1) и LOG|1–WIN|1 (пилот 2); NONE — с повторами LOG|1 и WIN|1 того же прогона пилота 2.
Мощность — нормальное приближение с t-квантилем при n задач теста: направленное по 95 % интервалу,
эквивалентность (TOST) по 90 % интервалу внутри ±δ. Ложный уровень — на границе: 0,025 у направленного
(истинное среднее 0), 0,05 у эквивалентности (истинная разность ±δ). Вес — log₂(мощность / ложный уровень), пол 0,001.
  python3 power_score01.py [--md]   → pilot_power.json и таблица"""
import json
import math
import os
import sys

from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from analyze_score01 import PRED, value, weights  # noqa: E402

N_TEST = dict(main=100, rep=99)
FLOOR = 0.001


def cells(model):
    E = json.load(open(os.path.join(HERE, 'evals', f'pilot12_{model}.json')))
    return E['rows'], sorted({r['task'] for r in E['rows'].values()})


def pilot_series(rows, tasks, p):
    """Значения цели одного вызова на задачу в пилоте. Без NONE — по двум повторам (|0 из пилота 1, |1 из пилота 2);
    с NONE — NONE|0 с повторами |1 остальных рук (тот же прогон пилота 2, вперемешку по задачам)."""
    m = p['measure']
    w = weights(p['target'])
    ok = lambda r: r and r['valid'] and not (m == 'auc' and math.isnan(r['auc']))
    layouts = [{a: '1' if a != 'NONE' else '0' for a in w}] if 'NONE' in w else [{a: '0' for a in w}, {a: '1' for a in w}]
    out = []
    for t in tasks:
        for lay in layouts:
            rs = {a: rows.get(f'{t}|{a}|{lay[a]}') for a in w}
            if all(ok(r) for r in rs.values()):
                out.append(sum(wa * value(rs[a], m) for a, wa in w.items()))
    return out


def power(p, mu, s, n):
    se = s / math.sqrt(n)
    if p['kind'] == 'equiv':
        t = stats.t.ppf(0.95, n - 1); d = p['margin']
        pw = stats.norm.cdf((d - mu) / se - t) + stats.norm.cdf((d + mu) / se - t) - 1
        return max(0.0, pw), 0.05
    t = stats.t.ppf(0.975, n - 1)
    z = (-mu if p['kind'] == 'lt0' else mu) / se
    return stats.norm.cdf(z - t), 0.025


def main():
    md = '--md' in sys.argv
    out = {}
    cache = {}
    if md:
        print('| | Модель | Мера | Что сравнивается | Предсказание | Пилот: среднее (SD; пар) | Мощность, n = 100 | При SD × 1,5 | Ложный уровень | Вес, бит |')
        print('|---|---|---|---|---|---|---|---|---|---|')
    for p in PRED:
        if p['model'] not in cache:
            cache[p['model']] = cells(p['model'])
        rows, tasks = cache[p['model']]
        x = pilot_series(rows, tasks, p)
        mu = sum(x) / len(x); s = math.sqrt(sum((v - mu) ** 2 for v in x) / (len(x) - 1))
        pw, a = power(p, mu, s, N_TEST['main'])
        pw15, _ = power(p, mu, 1.5 * s, N_TEST['main'])
        pw_rep, _ = power(p, mu, s, N_TEST['rep'])
        bits = math.log2(pw / max(a, FLOOR)) if pw > 0 else float('-inf')
        out[p['id']] = dict(model=p['model'], measure=p['measure'], target=p['target'], kind=p['kind'], margin=p.get('margin'),
                            pilot_mean=mu, pilot_sd=s, pilot_n=len(x), power=pw, power_sd15=pw15, power_rep=pw_rep, alpha=a, bits=bits)
        tg = p['target']
        what = (f'{tg[1]} − {tg[2]}' if tg[0] == 'pair' else f'рука {tg[1]}' if tg[0] == 'arm' else
                ' '.join(f"{'+' if w > 0 else '−'} {abs(w):g}·{a}" for a, w in tg[1].items()).lstrip('+ '))
        kind = {'lt0': '< 0', 'gt0': '> 0', 'equiv': f'|·| < {p.get("margin")}'}[p['kind']]
        f = lambda v, d=3: f'{v:.{d}f}'.replace('.', ',').replace('-', '−')
        if md:
            print(f"| {p['id']} | {p['model']} | {p['measure']} | {what} | {kind} | {f(mu)} ({f(s)}; {len(x)}) | {f(pw)} | {f(pw15)} | {f(a)} | {f(bits, 1)} |")
        else:
            print(p['id'], out[p['id']])
    json.dump(out, open(os.path.join(HERE, 'pilot_power.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
