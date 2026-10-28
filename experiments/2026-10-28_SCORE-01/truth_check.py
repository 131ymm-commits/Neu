#!/usr/bin/env python3
"""SCORE-01: устойчивость меток «в лучшей половине» к ошибке Монте-Карло правды (до регистрации; правило CLAUDE.md
«правду проверять вторым способом до прогона»; DESIGN: сверка sim.truth пересчётом с другим R).
Для каждой задачи выборки: значения 8 кандидатов на R = 4000 реализаций шума (первые 1000 — те же, что у sim.truth),
общие для кандидатов (общие случайные числа). Печатает:
  - совпадение пересчёта на первых 1000 с truth/<выборка>.json (код правды тот же);
  - четвёрку по R = 1000 против четвёрки по R = 4000 (сходимость);
  - z = разрыв 4-го и 5-го кандидата / SE парной разности при R = 1000 (общие случайные числа);
  - ничьи после округления до 0,01 на границе четвёрки.
  python3 truth_check.py pilot main rep → truth/check_<выборка>.json"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score01 as S  # noqa: E402

R_BIG = 4000


def check(sample):
    tru = json.load(open(os.path.join(HERE, 'truth', f'{sample}.json')))['tasks']
    salt = S.salt(sample)
    out = {}
    for t in S.sample_tasks(sample):
        tk, pl = S.task(t), S.pool(t)
        seeds = S.sim.noise_seeds(salt, tk['seed'], R_BIG)
        typ = tk['type']
        V = [[S.sim.SIM[typ](tk, c['plan'], S.sim.NOISE[typ](tk, s)) for s in seeds] for c in pl]
        m1 = [round(sum(v[:1000]) / 1000, 2) for v in V]
        m4 = [sum(v) / R_BIG for v in V]
        same_truth = m1 == tru[t]['truth']
        o1 = sorted(range(8), key=lambda i: (-m1[i], S.hkey(t, i)))
        o4 = sorted(range(8), key=lambda i: (-m4[i], S.hkey(t, i)))
        a, b = o1[3], o1[4]
        d = [x - y for x, y in zip(V[a][:1000], V[b][:1000])]
        md = sum(d) / 1000
        se = math.sqrt(sum((x - md) ** 2 for x in d) / 999 / 1000)
        out[t] = dict(same_truth=same_truth, top4_1000=sorted(o1[:4]), top4_4000=sorted(o4[:4]),
                      top4_same=set(o1[:4]) == set(o4[:4]), gap45=m1[a] - m1[b], se45=se,
                      z45=(m1[a] - m1[b]) / se if se > 0 else float('inf'), tie45=m1[a] == m1[b])
    n = len(out)
    zs = sorted(v['z45'] for v in out.values())
    summ = dict(sample=sample, n=n, same_truth=sum(v['same_truth'] for v in out.values()),
                top4_same=sum(v['top4_same'] for v in out.values()), tie45=sum(v['tie45'] for v in out.values()),
                z45_lt2=sum(1 for z in zs if z < 2), z45_lt1=sum(1 for z in zs if z < 1), z45_median=zs[n // 2])
    json.dump(dict(summary=summ, tasks=out), open(os.path.join(HERE, 'truth', f'check_{sample}.json'), 'w'), indent=0)
    print(summ, flush=True)


if __name__ == '__main__':
    for s in sys.argv[1:]:
        check(s)
