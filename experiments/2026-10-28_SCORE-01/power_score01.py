#!/usr/bin/env python3
"""SCORE-01: мощность и ложный уровень предсказаний PREREG по микропилоту 3 (чистый контекст; evals/pilot3_<модель>.json).
Предсказания — analyze_score01.PRED (одна копия). Пилот 3: 20 задач, руки LOG, WIN, NONE, по два вызова на клетку (повторы 0 и 1),
в одном прогоне, вызовы задачи вперемешку.
Цель — в том виде, в каком её даст тест:
  Opus (один вызов на клетку): значение задачи — по одному повтору k ∈ {0, 1} для всех рук цели (два варианта на задачу);
  Haiku (два вызова): значение задачи — по среднему двух повторов каждой руки (один вариант).
Мощность:
  «в точке» — нормальное приближение с t-квантилем при истинном эффекте = среднему пилота и SD пилота (верхняя оценка);
  «с неопределённостью пилота» — двухуровневый бутстреп (как у проверяльщика, lenses/scripts/assurance.py): пилотные задачи
  пересэмплируются, затем тест из n задач по букве анализа; так же — совместно для сводных.
Ложный уровень — на границе: 0,025 у направленного (истинное среднее 0), 0,05 у эквивалентности (истинная разность ±δ).
Вес — log₂(мощность с неопределённостью пилота / ложный уровень), пол ложного уровня 0,001.
  python3 power_score01.py [--md] [--B 4000]   → pilot_power.json и таблица"""
import json
import math
import os
import sys

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from analyze_score01 import PRED, REPS, value, weights  # noqa: E402

N_TEST = 100
FLOOR = 0.001
B = int(sys.argv[sys.argv.index('--B') + 1]) if '--B' in sys.argv else 4000
PILOT = 'pilot3'


def variants(model):
    """По задаче пилота — матрица вариантов значений всех предсказаний модели (строка — вариант «вызова теста»)."""
    R = json.load(open(os.path.join(HERE, 'evals', f'{PILOT}_{model}.json')))['rows']
    T = sorted({r['task'] for r in R.values()})
    ps = [p for p in PRED if p['model'] == model]
    ok = lambda r, m: r is not None and r['valid'] and not (m == 'auc' and math.isnan(r['auc']))
    per_task = []
    layouts = [('0',), ('1',)] if len(REPS[model]) == 1 else [('0', '1')]
    for t in T:
        rows = []
        for reps in layouts:
            row = []
            for p in ps:
                m, w = p['measure'], weights(p['target'])
                vals = {}
                for a in w:
                    v = [value(R[f'{t}|{a}|{k}'], m) for k in reps if ok(R.get(f'{t}|{a}|{k}'), m)]
                    if v:
                        vals[a] = sum(v) / len(v)
                row.append(sum(wa * vals[a] for a, wa in w.items()) if len(vals) == len(w) else np.nan)
            rows.append(row)
        per_task.append(np.array(rows, dtype=float))
    return ps, per_task


def verdict(x, p):
    x = x[~np.isnan(x)]
    n = len(x); m = x.mean(); s = x.std(ddof=1)
    if p['kind'] == 'equiv':
        h = stats.t.ppf(0.95, n - 1) * s / math.sqrt(n)
        return (m - h > -p['margin']) and (m + h < p['margin'])
    h = stats.t.ppf(0.975, n - 1) * s / math.sqrt(n)
    return (m + h < 0) if p['kind'] == 'lt0' else (m - h > 0)


def point_power(p, mu, s, n=N_TEST):
    se = s / math.sqrt(n)
    if p['kind'] == 'equiv':
        t = stats.t.ppf(0.95, n - 1); d = p['margin']
        return max(0.0, stats.norm.cdf((d - mu) / se - t) + stats.norm.cdf((d + mu) / se - t) - 1), 0.05
    t = stats.t.ppf(0.975, n - 1)
    z = (-mu if p['kind'] == 'lt0' else mu) / se
    return stats.norm.cdf(z - t), 0.025


def assurance(model, rng, n=N_TEST):
    ps, per_task = variants(model)
    K = len(per_task)
    comps = sorted({p['comp'] for p in ps if p['comp']})
    hits = np.zeros(len(ps)); chits = {c: 0 for c in comps}
    for _ in range(B):
        base = rng.integers(0, K, K)                              # пилот пересэмплирован: истина неизвестна
        idx = base[rng.integers(0, K, n)]
        X = np.array([per_task[i][rng.integers(0, len(per_task[i]))] for i in idx])
        okv = [verdict(X[:, j], p) for j, p in enumerate(ps)]
        hits += okv
        for c in comps:
            chits[c] += all(okv[j] for j, p in enumerate(ps) if p['comp'] == c)
    return {p['id']: hits[j] / B for j, p in enumerate(ps)}, {c: v / B for c, v in chits.items()}, ps, per_task


def main():
    md = '--md' in sys.argv
    rng = np.random.default_rng(20261029)
    out = dict(pilot=PILOT, B=B, n_test=N_TEST, preds={}, comps={})
    f = lambda v, d=3: f'{v:.{d}f}'.replace('.', ',').replace('-', '−')
    rows_md = []
    for model in ('opus', 'haiku'):
        if not any(p['model'] == model for p in PRED):
            continue
        a_un, c_un, ps, per_task = assurance(model, rng)
        for j, p in enumerate(ps):
            x = np.concatenate([v[:, j] for v in per_task]); x = x[~np.isnan(x)]
            mu, s = float(x.mean()), float(x.std(ddof=1))
            pw, a = point_power(p, mu, s)
            pw15, _ = point_power(p, mu, 1.5 * s)
            bits = math.log2(max(a_un[p['id']], 1e-9) / max(a, FLOOR))
            out['preds'][p['id']] = dict(model=model, measure=p['measure'], target=p['target'], kind=p['kind'], margin=p.get('margin'),
                                         pilot_mean=mu, pilot_sd=s, pilot_n=len(x), power_point=pw, power_point_sd15=pw15,
                                         power_assurance=a_un[p['id']], alpha=a, bits=bits)
            tg = p['target']
            what = (f'{tg[1]} − {tg[2]}' if tg[0] == 'pair' else f'рука {tg[1]}' if tg[0] == 'arm' else
                    ' '.join(f"{'+' if w > 0 else '−'} {f(abs(w), 1) + '·' if abs(w) != 1 else ''}{a_}" for a_, w in tg[1].items()).lstrip('+ '))
            kind = {'lt0': '< 0', 'gt0': '> 0', 'equiv': f'\\|·\\| < {f(p.get("margin") or 0, 2)}'}[p['kind']]
            d = 0 if p['measure'] == 'out' else 3
            rows_md.append(f"| {p['id']} | {model} | {p['measure']} | {what} | {kind} | {f(mu, d)} ({f(s, d)}; {len(x)}) | {f(pw)} | {f(pw15)} | "
                           f"{f(a_un[p['id']])} | {f(a)} | {f(bits, 1)} |")
        for c, v in c_un.items():
            parts = [p['id'] for p in ps if p['comp'] == c]
            a_ = max(out['preds'][i]['alpha'] for i in parts)
            out['comps'][c] = dict(parts=parts, alpha=a_, power_point_product=math.prod(out['preds'][i]['power_point'] for i in parts),
                                   power_assurance_joint=v, bits=math.log2(max(v, 1e-9) / max(a_, FLOOR)))
    json.dump(out, open(os.path.join(HERE, 'pilot_power.json'), 'w'), ensure_ascii=False, indent=1)
    if md:
        print('| | Модель | Мера | Что сравнивается | Предсказание | Пилот 3: среднее (SD; значений) | Мощность в точке | В точке при SD × 1,5 | С неопределённостью пилота | Ложный уровень | Вес, бит |')
        print('|---|---|---|---|---|---|---|---|---|---|---|')
        print('\n'.join(rows_md))
        print()
        print('| Сводный | Части | Ложный уровень | Мощность в точке (произведение) | С неопределённостью пилота (совместно) | Вес |')
        print('|---|---|---|---|---|---|')
        for c, v in out['comps'].items():
            print(f"| {c} | {', '.join(v['parts'])} | {f(v['alpha'])} | {f(v['power_point_product'])} | {f(v['power_assurance_joint'])} | {f(v['bits'], 1)} бита |")
    else:
        print(json.dumps(out['comps'], ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
