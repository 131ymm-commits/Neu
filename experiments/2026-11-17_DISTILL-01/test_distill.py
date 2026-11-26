#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-01: проверки кода на заглушках (головы с известной формулой ошибки). Ожидания — формулой, не прикидкой (ERRORS № 181).
  python3 test_distill.py"""
import json
import math
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import distill as D  # noqa: E402

FAIL = []


def check(name, ok, info=''):
    print(('✓ ' if ok else '✗ ') + name + (f' — {info}' if info and not ok else ''))
    if not ok:
        FAIL.append(name)


# 1. Признаки по известным примерам
f = D.features(999, 11, 9)                          # 999 + 11 = 1010: три переноса подряд, старший — в разряде сотен (2), сумма длиннее a
check('признаки: 999 + 11', f == dict(nd_a=3, carries=3, new_place=1, top_carry=2, chain=3, nines=3, ood=1), str(f))
f = D.features(120, 15, 1)                          # 135: переносов нет; граница 100·(1+1) = 200 → в диапазоне
check('признаки: 120 + 15', f == dict(nd_a=3, carries=0, new_place=0, top_carry=-1, chain=0, nines=0, ood=0), str(f))
f = D.features(1905, 96, 19)                        # 2001: 5+6 перенос, 0+9+1 перенос, 9+0+1 перенос, 1+0+1 = 2 — цепочка 3
check('признаки: 1905 + 96', f['carries'] == 3 and f['chain'] == 3 and f['top_carry'] == 2 and f['new_place'] == 0 and f['ood'] == 1, str(f))

# 2. Виды ошибки
check('виды ошибки', [D.kind(1000, 1010), D.kind(1110, 1010), D.kind(110, 1010), D.kind(1013, 1010)]
      == ['потеря переноса', 'лишний перенос', 'потеря разряда', 'прочее'])

# 3. Ложное большинство при независимых головах = G(p) = 7p⁶ − 6p⁷ (docs/2026-11-17_T4_formula.md)
for p in (0.2, 0.5, 0.8, 0.95):
    g = 7 * p ** 6 - 6 * p ** 7
    check(f'ложное большинство при p = {p}: равно 7p⁶ − 6p⁷', abs(D.false_major_indep([p] * 7) - g) < 1e-12)

# 4. Заглушка: семь голов, ошибка ~ σ(−3 + 1,2·carries + 2·ood), независимо при данной задаче
rng = np.random.default_rng(3)
tmp = tempfile.mkdtemp(prefix='distill_stub_')
TRUE = (-3.0, 1.2, 2.0)


def make(phase_dir, X_list, n, seed):
    g = np.random.default_rng(seed)
    shared = {X: [[int(100 * X + g.integers(0, 100)), int(g.integers(10, 100))] for _ in range(n)] for X in X_list}   # задачи общие для голов
    for k in range(7):
        envs, cols = [], {}
        for X in X_list:
            keys = shared[X]
            name = f'S_X{X}'
            envs.append(dict(name=name, X=X, p=1, keys=keys))
            c = dict(answer=[], correct=[], logp=[], n_tok=[], text_none={})
            for a, b in keys:
                ft = D.features(a, b, X)
                pe = 1 / (1 + math.exp(-(TRUE[0] + TRUE[1] * ft['carries'] + TRUE[2] * ft['ood'])))
                err = g.random() < pe
                c['answer'].append(a + b - 10 if err else a + b)
                c['correct'].append(int(not err))
                c['logp'].append(float(-g.random() * (2.0 if err else 0.5)))
                c['n_tok'].append(4)
            cols[name] = c
        d = os.path.join(phase_dir, f'h{k}')
        os.makedirs(d, exist_ok=True)
        json.dump(dict(model=f'stub/H{k}', envs=envs, cols=cols), open(os.path.join(d, 'answers_H.json'), 'w'))


make(os.path.join(tmp, 'fit'), (4, 6, 9, 19), 300, 1)
make(os.path.join(tmp, 'hold'), (5, 7, 29), 300, 2)
an = dict(envs={'S_X29': dict(crowd=[f'H{k}' for k in range(7)], T4=dict(point=0.0, F=0.0, F0=0.0))})
json.dump(an, open(os.path.join(tmp, 'an.json'), 'w'))
res = D.main([os.path.join(tmp, 'out.json'), '--fit', os.path.join(tmp, 'fit', '*', 'answers_*.json'),
              '--hold', 'hold=' + os.path.join(tmp, 'hold', '*', 'answers_*.json'), '--t4', 'hold=' + os.path.join(tmp, 'an.json')])
fm = res['formulas']
check('формулы: у всех семи голов найдены carries и ood', all({'carries', 'ood'} <= set(v['feats']) for v in fm.values()),
      str({h: v['feats'] for h, v in fm.items()}))
check('формулы: не больше 3 признаков', all(len(v['feats']) <= 3 for v in fm.values()))
ok_signs = all(v['coef'][1 + v['feats'].index('carries')] > 0 and v['coef'][1 + v['feats'].index('ood')] > 0 for v in fm.values()
               if {'carries', 'ood'} <= set(v['feats']))
check('формулы: знаки carries и ood положительные', ok_signs)
co = [v['coef'][1 + v['feats'].index('carries')] for v in fm.values() if 'carries' in v['feats']]
check('формулы: коэффициент carries около 1,2 (в среднем по головам, допуск 0,3)', abs(np.mean(co) - TRUE[1]) < 0.3, str(np.round(co, 2)))
check('округление: две значащие цифры', D.round2(1.2345) == 1.2 and D.round2(-0.031416) == -0.031 and D.round2(0) == 0)
ev = res['hold']['hold']['eval']
check('отложенные: AUC формулы > 0,7 у всех голов', all(e['auc_formula'] > 0.7 for e in ev.values()), str({h: round(e['auc_formula'], 3) for h, e in ev.items()}))
check('отложенные: формула лучше константы по лог-потерям', all(e['ll_formula'] > e['ll_const'] for e in ev.values()))
ph = res['hold']['hold']['phi']
sh = [v['share'] for v in ph.values() if v['share'] is not None]
check('условная независимость: φ из формул ≈ фактическому (доля от 0,6 до 1,4)', sh and all(0.6 < s < 1.4 for s in sh), str(np.round(sh, 2)))
t4 = res['hold']['hold']['t4']['S_X29']
check('Т4 из формул посчитан и конечен', np.isfinite(t4['T4_pred']) and t4['crowd'] == 7, str(t4))
check('json пишется', os.path.exists(os.path.join(tmp, 'out.json')))
print('провалов:', len(FAIL))
sys.exit(1 if FAIL else 0)
