#!/usr/bin/env python3
"""Цена и мощность чистого повтора части SELECT-01 rep (аудит канала снимка git, ERRORS № 118): по журналам rep_eval и по
per_task анализов SELECT-01. Головы не вызываются. Запуск из корня репозитория:
  python3 journal/AUDIT_GIT_SNAPSHOT_2026-10-29_cost.py"""
import collections
import glob
import json
import math
import os

from scipy import stats

S = 'experiments/2026-10-07_SELECT-01'
cnt, cost, out = collections.Counter(), collections.defaultdict(float), collections.defaultdict(int)
for fn in glob.glob(os.path.join(S, 'run', 'rep_eval_journal', '*.jsonl')):
    for line in open(fn, encoding='utf-8'):
        r = json.loads(line)
        if r.get('final'):
            a = r.get('arm') or r['job'].split('|')[1]
            cnt[a] += 1; cost[a] += (r.get('usage') or {}).get('cost_usd') or 0; out[a] += (r.get('usage') or {}).get('out') or 0
print('Повтор SELECT-01, оценщики (итоговые записи журнала rep_eval; цена — поле cost_usd CLI, в пересчёте на API):')
for a in sorted(cnt):
    print(f'  {a}: вызовов {cnt[a]}, цена {cost[a]:.2f} $, выход в среднем {out[a] / cnt[a]:.0f} токенов')
need = ('D_N', 'B_blind')
print(f'  для чистого повтора D_N против B_blind (A0 вызовов не требует): вызовов {sum(cnt[a] for a in need)}, '
      f'цена около {sum(cost[a] for a in need):.0f} $')
eff = {}
for s in ('main', 'rep'):
    pt = json.load(open(os.path.join(S, f'{s}_an_wh.json')))['per_task']
    d = [v['D_N'] - v['B_blind'] for v in pt.values()]
    n = len(d); m = sum(d) / n; sd = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1))
    eff[s] = (n, m, sd)
    print(f'{s}: D_N − B_blind, задач {n}, среднее {m:.3f}, SD {sd:.3f}')
sd = eff['rep'][2]
for n in (50, 99):
    for lab, s in (('при эффекте повтора', 'rep'), ('при эффекте основной выборки', 'main')):
        z = abs(eff[s][1]) / (sd / math.sqrt(n))
        print(f'мощность одностороннего теста (α 0,025 — первый шаг Холма), {n} задач, {lab}: {stats.norm.cdf(z - stats.norm.ppf(0.975)):.2f}')
