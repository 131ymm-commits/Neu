#!/usr/bin/env python3
"""SCORE-02: теснота пулов у границы четвёрки (PREREG §8; LENSES-1, L3-7) — описательно, до регистрации.
Отношение разрыва 4-го и 5-го кандидатов к размаху правды пула (лучший − худший), по задачам; медиана и квартили.
Пилот — правда SCORE-01 по R = 1000 (`../2026-10-28_SCORE-01/truth/pilot.json`, поле truth; правды пилота по R = 4000 в файлах нет);
основная выборка и повтор — truth4000 и truth1000 (`truth/<выборка>.json`).
  python3 pool_gaps_score02.py   → truth/pool_gaps.json и печать (журнал — truth/pool_gaps.log)"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SC1 = os.path.join(HERE, '..', '2026-10-28_SCORE-01')


def ratio(v):
    s = sorted(v, reverse=True)
    rng = s[0] - s[-1]
    return (s[3] - s[4]) / rng if rng > 0 else float('nan')


def summary(rs):
    rs = [r for r in rs if r == r]
    return dict(n=len(rs), median=float(np.median(rs)), q25=float(np.quantile(rs, 0.25)), q75=float(np.quantile(rs, 0.75)))


def main():
    out, log = {}, []
    ids = {f'WH_{s}' for s in list(range(7001, 7013)) + list(range(7301, 7309))}   # 20 задач пилота SCORE-02 (score02.IDS['pilot'])
    P = json.load(open(os.path.join(SC1, 'truth', 'pilot.json')))['tasks']
    out['pilot_R1000'] = summary([ratio(v['truth']) for t, v in P.items() if t in ids])
    for smp in ('main', 'rep'):
        T = json.load(open(os.path.join(HERE, 'truth', f'{smp}.json')))['tasks']
        out[f'{smp}_R4000'] = summary([ratio(v['truth4000']) for v in T.values()])
        out[f'{smp}_R1000'] = summary([ratio(v['truth1000']) for v in T.values()])
    for k, v in out.items():
        log.append(f"{k}: задач {v['n']}, медиана отношения «разрыв 4-го и 5-го / размах пула» {v['median']:.3f} (квартили {v['q25']:.3f}–{v['q75']:.3f})")
    json.dump(out, open(os.path.join(HERE, 'truth', 'pool_gaps.json'), 'w'), indent=1)
    open(os.path.join(HERE, 'truth', 'pool_gaps.log'), 'w', encoding='utf-8').write('\n'.join(log) + '\n')
    print('\n'.join(log))


if __name__ == '__main__':
    main()
