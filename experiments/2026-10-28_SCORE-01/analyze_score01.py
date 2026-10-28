#!/usr/bin/env python3
"""SCORE-01: вердикты по букве PREREG из evals/<этап>.json (меры считает score01.py metrics … half).
  python3 analyze_score01.py [--stages main_opus,main_haiku,rep_opus,rep_haiku] [--out analysis_score01.json] [--evals evals]
Единица — задача; разности рук — парные по задачам (обе клетки годны). Интервалы — t-интервал среднего парной
разности (95 % для направленных предсказаний, 90 % для эквивалентности TOST); p перестановки знаков — оценка
Монте-Карло (100 000 перестановок, зерно — crc32 имени предсказания). Вердикт — только по интервалу.
Исходы: «подтверждено» — интервал целиком на предсказанной стороне (эквивалентность: 90 % интервал внутри ±δ);
«опровергнуто» — интервал целиком на другой стороне (эквивалентность: 90 % интервал целиком вне ±δ); «не показано» — иначе;
«не показано (потери)» — годных пар меньше 90 % задач выборки.
Сводный исход (по выборке): «подтверждено» — все части подтверждены; «опровергнуто» — хоть одна опровергнута;
иначе «не подтверждено». «Установлено» (ключ status) — сводный подтверждён и в основной выборке, и в повторе, и
сводный разрешено так называть (ESTABLISH); иначе статус по основной выборке."""
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

# --- предсказания: замораживаются в PREREG ---
# kind: 'lt0' — разность (или величина) < 0; 'gt0' — > 0; 'equiv' — |разность| < margin (TOST, 90 %).
# target: ('pair', 'WIN', 'LOG') — разность WIN − LOG по задачам; ('arm', 'LOG') — величина руки (одновыборочно);
#         ('contrast', {рука: вес}) — Σ вес·величина по задаче.
# comp — сводный исход (None — разведка, вне семьи); expect — моя вероятность подтверждения (после пилота).
RULE = ('contrast', {'LOG': 0.5, 'WIN': 0.5, 'NONE': -1.0})          # объявление правила (среднее LOG и WIN) − NONE
P = lambda **k: k
PRED = [
    P(id='O1', model='opus', measure='self_dec', target=('pair', 'WIN', 'LOG'), kind='equiv', margin=0.1, comp='SA_opus', expect=0.85,
      text='самообман WIN − LOG в пределах ±0,1'),
    P(id='O2', model='opus', measure='acc', target=('pair', 'WIN', 'LOG'), kind='equiv', margin=0.1, comp='SA_opus', expect=0.85,
      text='точность WIN − LOG в пределах ±0,1'),
    P(id='O3', model='opus', measure='brier', target=('pair', 'WIN', 'LOG'), kind='equiv', margin=0.05, comp='SA_opus', expect=0.9,
      text='Брайер WIN − LOG в пределах ±0,05'),
    P(id='O4', model='opus', measure='self_dec', target=('arm', 'LOG'), kind='gt0', comp='SB_opus', expect=0.95,
      text='самообман LOG > 0'),
    P(id='O5', model='opus', measure='self_dec', target=('arm', 'WIN'), kind='gt0', comp='SB_opus', expect=0.95,
      text='самообман WIN > 0'),
    P(id='O6', model='opus', measure='self_dec', target=('arm', 'NONE'), kind='gt0', comp='SB_opus', expect=0.95,
      text='самообман NONE > 0'),
    P(id='O7', model='opus', measure='acc', target=RULE, kind='gt0', comp='SC_opus', expect=0.5,
      text='точность (LOG + WIN)/2 − NONE > 0'),
    P(id='O8', model='opus', measure='out', target=RULE, kind='gt0', comp='SD_opus', expect=0.85,
      text='выходные токены (LOG + WIN)/2 − NONE > 0'),
    P(id='OE1', model='opus', measure='conf', target=('pair', 'WIN', 'LOG'), kind='lt0', comp=None, expect=0.6,
      text='разведка: уверенность WIN − LOG < 0'),
    P(id='OE2', model='opus', measure='self_dec', target=('contrast', {'NONE': 1.0, 'LOG': -0.5, 'WIN': -0.5}), kind='gt0', comp=None,
      expect=0.45, text='разведка: самообман NONE − (LOG + WIN)/2 > 0'),
    P(id='OE3', model='opus', measure='auc', target=RULE, kind='gt0', comp=None, expect=0.45,
      text='разведка: AUC (LOG + WIN)/2 − NONE > 0'),
]
PRED_HAIKU = []          # заполняется после микропилота 2 Haiku
PRED += PRED_HAIKU
# сводные: части — по comp; ESTABLISH — можно ли назвать «установлено» при подтверждении в обеих выборках
ESTABLISH = dict(SA=True, SB=True, SC=False, SD=False)
COMP_TEXT = dict(
    SA='тип объявленного правила (LOG или WIN) не меняет самообман и точность оценщика больше чем на 0,1 и Брайер больше чем на 0,05',
    SB='самообман оценщика (уверенность выше точности) есть в каждой руке, и при объявленном правиле, и без него',
    SC='объявление правила (любого из двух) повышает точность оценщика по сравнению с промптом без правила',
    SD='объявление правила (любого из двух) удлиняет рассуждение по сравнению с промптом без правила')


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
        out = 'подтверждено' if (lo > -d and hi < d) else ('опровергнуто' if (lo >= d or hi <= -d) else 'не показано')
        m95, lo95, hi95, _ = t_ci(x, 0.95)
        return dict(outcome=out, n=len(x), n_tasks=n_tasks, mean=m, ci90=[lo, hi], ci95=[lo95, hi95], sd=s, margin=d,
                    p_perm_two_sided=perm_p(x, name))
    m, lo, hi, s = t_ci(x, 0.95)
    if p['kind'] == 'lt0':
        out = 'подтверждено' if hi < 0 else ('опровергнуто' if lo > 0 else 'не показано')
    else:
        out = 'подтверждено' if lo > 0 else ('опровергнуто' if hi < 0 else 'не показано')
    return dict(outcome=out, n=len(x), n_tasks=n_tasks, mean=m, ci95=[lo, hi], sd=s,
                p_perm_two_sided=perm_p(x, name) if p['target'][0] != 'arm' else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stages', default='main_opus,main_haiku,rep_opus,rep_haiku')
    ap.add_argument('--out', default=os.path.join(HERE, 'analysis_score01.json'))
    ap.add_argument('--evals', default=os.path.join(HERE, 'evals'), help='папка с evals (для сухого прогона — dry/evals)')
    a = ap.parse_args()
    res = dict(stages={}, verdicts={}, composites={}, status={}, n_perm=N_PERM, pred=PRED)
    for st in a.stages.split(','):
        path = os.path.join(a.evals, f'{st}.json')
        if not os.path.exists(path):
            print('нет', path)
            continue
        E = json.load(open(path))
        assert E.get('labels') == 'r4000', f'{st}: метки должны быть по 4000 реализациям (score01.py metrics … half4)'
        sample, model = st.split('_', 1)
        res['stages'][st] = dict(summary=E['summary'], paired=E.get('paired'), labels=E.get('labels'))
        for p in PRED:
            if p['model'] != model:
                continue
            v = verdict(p, E)
            res['verdicts'][f"{p['id']}|{st}"] = v
            ci = v.get('ci90') if p['kind'] == 'equiv' else v.get('ci95')
            print(f"{p['id']:6s} {st:11s} {p['measure']:9s} {str(p['target']):24s} {p['kind']:5s} → {v['outcome']}"
                  + (f"; среднее {v['mean']:+.4f} [{ci[0]:+.4f}; {ci[1]:+.4f}], n {v['n']}" if 'mean' in v else ''))
        for comp in sorted({p['comp'] for p in PRED if p['comp'] and p['model'] == model}):
            parts = [p['id'] for p in PRED if p['comp'] == comp]
            outs = [res['verdicts'][f'{i}|{st}']['outcome'] for i in parts]
            o = 'подтверждено' if all(x == 'подтверждено' for x in outs) else (
                'опровергнуто' if any(x == 'опровергнуто' for x in outs) else 'не подтверждено')
            res['composites'][f'{comp}|{st}'] = dict(parts=parts, outcome=o)
            print(f'сводный {comp} {st}: {o} ({", ".join(f"{i} {x}" for i, x in zip(parts, outs))})')
    for comp in sorted({p['comp'] for p in PRED if p['comp']}):
        model = comp.split('_', 1)[1]
        m_, r_ = res['composites'].get(f'{comp}|main_{model}'), res['composites'].get(f'{comp}|rep_{model}')
        if m_ is None:
            continue
        both = r_ is not None and m_['outcome'] == r_['outcome'] == 'подтверждено'
        st_ = ('установлено' if ESTABLISH[comp.split('_')[0]] else 'подтверждено (повторено; причина не проверялась)') if both else (
            m_['outcome'] + ('' if r_ is None else f'; повтор: {r_["outcome"]}'))
        res['status'][comp] = dict(main=m_['outcome'], rep=None if r_ is None else r_['outcome'], status=st_)
        print(f'статус {comp}: {st_}')
    json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print('→', a.out)


if __name__ == '__main__':
    main()
