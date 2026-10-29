#!/usr/bin/env python3
"""Аудит канала «снимок git» (ERRORS № 118), дополнение 29.10.2026: какие вызовы повторов и проверок видели в «Recent commits»
коммит с исходом основной выборки. CLI 2.1.294 кладёт в контекст `git log --oneline -n 5` на старте каждого вызова
(LENSES-1 SCORE-01, L1-1), а контрольные точки журналов во время прогона вытесняли старые коммиты из пятёрки.
Пятёрка на момент старта вызова — пять последних коммитов текущей ветки по дате коммита (история линейная) с датой не позже старта.
  python3 journal/AUDIT_GIT_SNAPSHOT_2026-10-29_exposure.py   → journal/AUDIT_GIT_SNAPSHOT_2026-10-29_exposure.json и печать"""
import collections
import datetime as dt
import glob
import json
import os
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CASES = [  # журнал, коммиты с исходом или его признанием (из таблицы аудита)
    ('experiments/2026-10-07_SELECT-01/run/rep_eval_journal', ['35fc0e4', '24bc4ee']),
    ('experiments/2026-10-15_THINK-01/run/rep_eval_high_journal', ['975efbd', '939e6df']),
    ('experiments/2026-10-15_THINK-01/run/rep_eval_medium_journal', ['975efbd', '939e6df']),
    ('experiments/2026-10-21_PRECOND-01/run/val_eval_medium_journal', ['c98b937', 'dda6ae2']),
]


def commits():
    out = subprocess.run(['git', 'log', '--first-parent', '--format=%h %cI'], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return sorted((dt.datetime.fromisoformat(l.split()[1]), l.split()[0][:7]) for l in out.splitlines() if l.strip())


def main():
    C = commits()
    times = [c[0] for c in C]
    import bisect
    res = {}
    for j, watch in CASES:
        per = collections.defaultdict(collections.Counter)
        n = 0
        for p in glob.glob(os.path.join(ROOT, j, '*.jsonl')):
            if os.path.basename(p) == 'run_log.jsonl':
                continue
            for l in open(p, encoding='utf-8'):
                r = json.loads(l)
                if not r.get('final'):
                    continue
                n += 1
                t = dt.datetime.fromisoformat(r['started'])
                k = bisect.bisect_right(times, t)
                top = [h for _, h in C[max(0, k - 5):k]]
                per[r['task']]['calls'] += 1
                for w in watch:
                    per[r['task']][w] += w in top
        tasks = sorted(per)
        res[j] = dict(calls=n, tasks=len(tasks), watch=watch,
                      exposed={w: dict(tasks=[t for t in tasks if per[t][w]], calls=sum(per[t][w] for t in tasks)) for w in watch},
                      per_task={t: dict(per[t]) for t in tasks})
        print(f'{j}: итоговых вызовов {n}, задач {len(tasks)}')
        for w in watch:
            e = res[j]['exposed'][w]
            print(f'  {w} в пятёрке: вызовов {e["calls"]}, задач хоть с одним таким вызовом {len(e["tasks"])}'
                  + (f' ({e["tasks"][0]} … {e["tasks"][-1]})' if e['tasks'] else ''))
    json.dump(res, open(os.path.join(ROOT, 'journal', 'AUDIT_GIT_SNAPSHOT_2026-10-29_exposure.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
