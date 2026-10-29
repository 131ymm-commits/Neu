#!/usr/bin/env python3
"""SCORE-01: таблицы пилотов из evals/<этап>.json (числа в PILOT*.md — командой, не перепечаткой).
  python3 pilot_tables.py pilot1_opus pilot1_haiku"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
f = lambda x, d=3: '—' if x is None else f'{x:.{d}f}'.replace('.', ',').replace('-', '−')


def main():
    print('| Этап | Рука | Годных | Точность | Уверенность | Самообман | AUC (по всем) | Брайер | Лог-потеря | ИОИ = незнание + самообман | Выход, ток. | Цена вызова, $ |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|')
    for st in sys.argv[1:]:
        E = json.load(open(os.path.join(HERE, 'evals', f'{st}.json')))
        for arm, s in E['summary'].items():
            print(f"| {st} | {arm} | {s['n']} из {s['n'] + s['invalid']} | {f(s['acc'])} | {f(s['conf'])} | {f(s['self_dec'])} | {f(s['auc_pooled'])} | "
                  f"{f(s['brier'])} | {f(s['logloss'])} | {f(s['ioi'])} = {f(s['ignorance'])} + {f(s['deception'])} | {s['out']:.0f} | {f(s['cost'], 4)} |")
    print()
    print('| Этап | Разность по задачам | Уверенность | Точность | Самообман | Брайер | Лог-потеря | ИОИ |')
    print('|---|---|---|---|---|---|---|---|')
    for st in sys.argv[1:]:
        E = json.load(open(os.path.join(HERE, 'evals', f'{st}.json')))
        for name, pd in (E.get('paired') or {'WIN_minus_LOG': E['paired_WIN_minus_LOG']}).items():
            cell = lambda k: f"{f(pd[k]['mean'])} ± {f(pd[k]['sd'])}" if k in pd else '—'
            print(f"| {st} | {name.replace('_minus_', ' − ')} (n = {pd['conf']['n']}; среднее ± SD) | {cell('conf')} | {cell('acc')} | {cell('self_dec')} | "
                  f"{cell('brier')} | {cell('logloss')} | {cell('ioi')} |")


if __name__ == '__main__':
    main()
