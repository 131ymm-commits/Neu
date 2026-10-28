#!/usr/bin/env python3
"""SCORE-01: вердикты по букве PREREG из evals/<этап>.json (меры считает score01.py metrics … half).
  python3 analyze_score01.py [--stages main_opus,main_haiku,rep_opus,rep_haiku] [--out analysis_score01.json]
Единица — задача; разности рук — парные по задачам (обе клетки годны). Интервалы — t-интервал среднего парной
разности (95 % для направленных предсказаний, 90 % для эквивалентности TOST); p перестановки знаков — оценка
Монте-Карло (100 000 перестановок, зерно — crc32 имени предсказания). Вердикт — только по интервалу.
Исходы: «подтверждено» — интервал целиком на предсказанной стороне (эквивалентность: 90 % интервал внутри ±δ);
«обратное» — интервал целиком на другой стороне (контрпрогноз теории); «не показано» — иначе;
«не показано (потери)» — годных пар меньше 90 % задач выборки."""
import argparse
import json
import math
import os
import random
import zlib

from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
MEASURES = ('acc', 'conf', 'self_dec', 'brier', 'logloss', 'auc', 'ioi', 'ignorance', 'deception')
N_PERM = 100_000
MIN_VALID_SHARE = 0.9

# --- предсказания: замораживаются в PREREG (заполняются после микропилота 2) ---
# kind: 'lt0' — разность (или величина) < 0; 'gt0' — > 0; 'equiv' — |разность| < margin (TOST, 90 %).
# target: ('pair', 'WIN', 'LOG') — разность WIN − LOG по задачам; ('arm', 'LOG') — величина руки (одновыборочно).
PRED = []


def value(row, m):
    if m == 'self_dec':
        return row['conf'] - row['acc']
    if m == 'out':
        return float(row['out'])           # выходные токены вызова (мера хода работы, не правды)
    return row[m]


def t_ci(x, level):
    n = len(x)
    m = sum(x) / n
    s = math.sqrt(sum((v - m) ** 2 for v in x) / (n - 1)) if n > 1 else float('nan')
    h = float(stats.t.ppf(0.5 + level / 2, n - 1)) * s / math.sqrt(n)
    return m, m - h, m + h, s


def perm_p(x, name):
    """Двусторонний p перестановки знаков для среднего (оценка Монте-Карло)."""
    rng = random.Random(zlib.crc32(name.encode()))
    obs = abs(sum(x))
    hits = sum(1 for _ in range(N_PERM) if abs(sum(v if rng.random() < 0.5 else -v for v in x)) >= obs - 1e-12)
    return (hits + 1) / (N_PERM + 1)


def weights(target):
    """Цель предсказания как веса рук: ('pair', A, B) — A − B; ('arm', A) — A; ('contrast', {A: w, …}) — Σ w·A."""
    if target[0] == 'pair':
        return {target[1]: 1.0, target[2]: -1.0}
    if target[0] == 'arm':
        return {target[1]: 1.0}
    return dict(target[1])


def series(E, target, m, rep='0'):
    """Значение цели по задачам; задача входит, если годны все её клетки (рука|rep)."""
    rows = E['rows']
    tasks = sorted({r['task'] for r in rows.values()})
    w = weights(target)
    out = []
    for t in tasks:
        rs = {a: rows.get(f'{t}|{a}|{rep}') for a in w}
        if all(r and r['valid'] and not (m == 'auc' and math.isnan(r['auc'])) for r in rs.values()):
            out.append(sum(wa * value(rs[a], m) for a, wa in w.items()))
    return out, len(tasks)


def verdict(p, E):
    x, n_tasks = series(E, p['target'], p['measure'])
    name = f"{p['id']}|{E['stage']}"
    if len(x) < MIN_VALID_SHARE * n_tasks or len(x) < 3:
        return dict(outcome='не показано (потери)', n=len(x), n_tasks=n_tasks)
    if p['kind'] == 'equiv':
        m, lo, hi, s = t_ci(x, 0.90)
        d = p['margin']
        out = 'подтверждено' if (lo > -d and hi < d) else 'не показано'
        m95, lo95, hi95, _ = t_ci(x, 0.95)
        return dict(outcome=out, n=len(x), n_tasks=n_tasks, mean=m, ci90=[lo, hi], ci95=[lo95, hi95], sd=s, margin=d,
                    p_perm_two_sided=perm_p(x, name))
    m, lo, hi, s = t_ci(x, 0.95)
    if p['kind'] == 'lt0':
        out = 'подтверждено' if hi < 0 else ('обратное' if lo > 0 else 'не показано')
    else:
        out = 'подтверждено' if lo > 0 else ('обратное' if hi < 0 else 'не показано')
    return dict(outcome=out, n=len(x), n_tasks=n_tasks, mean=m, ci95=[lo, hi], sd=s,
                p_perm_two_sided=perm_p(x, name) if p['target'][0] != 'arm' else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stages', default='main_opus,main_haiku,rep_opus,rep_haiku')
    ap.add_argument('--out', default=os.path.join(HERE, 'analysis_score01.json'))
    a = ap.parse_args()
    res = dict(stages={}, verdicts={}, n_perm=N_PERM, pred=PRED)
    for st in a.stages.split(','):
        path = os.path.join(HERE, 'evals', f'{st}.json')
        if not os.path.exists(path):
            print('нет', path)
            continue
        E = json.load(open(path))
        model = st.split('_', 1)[1]
        res['stages'][st] = dict(summary=E['summary'], paired=E.get('paired'))
        for p in PRED:
            if p['model'] != model:
                continue
            v = verdict(p, E)
            res['verdicts'][f"{p['id']}|{st}"] = v
            ci = v.get('ci90') if p['kind'] == 'equiv' else v.get('ci95')
            print(f"{p['id']:6s} {st:11s} {p['measure']:9s} {str(p['target']):24s} {p['kind']:5s} → {v['outcome']}"
                  + (f"; среднее {v['mean']:+.4f} [{ci[0]:+.4f}; {ci[1]:+.4f}], n {v['n']}" if 'mean' in v else ''))
    json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print('→', a.out)


if __name__ == '__main__':
    main()
