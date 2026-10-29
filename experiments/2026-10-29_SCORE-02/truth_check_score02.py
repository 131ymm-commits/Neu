#!/usr/bin/env python3
"""SCORE-02: правда вторым способом до прогона (CLAUDE.md). Для каждой задачи выборки:
  - среднее первых 1000 реализаций (truth1000 в truth/<выборка>.json, считал score02.py truth) совпадает с sim.truth SELECT-01
    (своя функция правды симулятора, R = 1000, округление до 0,01) — код правды тот же;
  - четвёрка по R = 4000 против четвёрки по R = 1000 (сходимость);
  - z45 — разрыв 4-го и 5-го кандидата / SE парной разности при R = 4000 (общие случайные числа): где метки шатки.
Головы не вызываются; соли — salts/<выборка>_salt.txt.
  python3 truth_check_score02.py main rep   → truth/check_<выборка>.json и печать (журнал — truth/truth_check.log: файлы run/ без pilot в имени verify-plans считает прогоном)"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score02 as S  # noqa: E402


def check(sample):
    T = json.load(open(os.path.join(HERE, 'truth', f'{sample}.json'), encoding='utf-8'))
    s = S.salt(sample)
    out = {}
    for t, v in T['tasks'].items():
        tk, pl = S.task(t), S.pool(t)
        tr = [S.sim.truth(tk, c['plan'], s) for c in pl]
        out[t] = dict(same_truth1000=[round(x, 2) for x in tr] == v['truth1000'], top4_same=v['top4_4000'] == v['top4_1000'],
                      z45=v['z45_4000'])
    zs = sorted(x['z45'] for x in out.values() if x['z45'] is not None)
    n = len(out)
    summ = dict(sample=sample, n=n, same_truth1000=sum(x['same_truth1000'] for x in out.values()),
                top4_same=sum(x['top4_same'] for x in out.values()), z45_lt2=sum(1 for z in zs if z < 2), z45_lt1=sum(1 for z in zs if z < 1),
                z45_median=zs[len(zs) // 2] if zs else None)
    json.dump(dict(summary=summ, tasks=out), open(os.path.join(HERE, 'truth', f'check_{sample}.json'), 'w', encoding='utf-8'), indent=0)
    return summ


def main():
    lines = []
    for smp in sys.argv[1:]:
        s = check(smp)
        lines.append(f"{smp}: задач {s['n']}; sim.truth (R = 1000) совпала у {s['same_truth1000']}; четвёрка по 4000 = по 1000 у {s['top4_same']}; "
                     f"z45 < 2 у {s['z45_lt2']}, < 1 у {s['z45_lt1']}; медиана z45 " + f"{s['z45_median']:.2f}".replace('.', ','))
    print('\n'.join(lines))
    open(os.path.join(HERE, 'truth', 'truth_check.log'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
