#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04: числа PREREG — только из json (ERRORS № 200, 226). Правило активности (как DISTILL-02): правило решающее, если решающая
мощность по пилоту не меньше POWER_MIN (у двустороннего — «подтверждено» + «опровергнуто», у одностороннего — «подтверждено»); замок —
сверка с test_d4.RULES_ACTIVE. Ожидания — 0,95 × решающая мощность; вес — log₂(мощность / α) и log₂((1 − мощность)/(1 − α)).
  python3 prereg_numbers_d4.py [--write]"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import test_d4 as T  # noqa: E402

POWER_MIN = 0.2
LEVEL = 0.0025
P2 = os.path.join(ROOT, 'gha_out/distill04_pilot2/pilot.json')
E3 = os.path.join(ROOT, 'experiments/2026-11-19_DISTILL-03/expect_d3.json')
SHORT = {'Falcon3-1B-Instruct': 'Falcon 1B', 'OLMo-2-0425-1B-Instruct': 'OLMo 1B', 'Qwen2.5-0.5B-Instruct': 'Qwen 0,5B',
         'Qwen2.5-1.5B-Instruct': 'Qwen 1,5B', 'SmolLM2-1.7B-Instruct': 'SmolLM 1,7B', 'SmolLM2-360M-Instruct': 'SmolLM 360M',
         'TinyLlama-1.1B-Chat-v1.0': 'TinyLlama 1,1B'}


def r(x, n=4, sign=False):
    s = f'{x:+.{n}f}' if sign else f'{x:.{n}f}'
    return s.replace('-', '−').replace('.', ',')


def main(a):
    p = json.load(open(P2, encoding='utf-8'))
    e3 = json.load(open(E3, encoding='utf-8'))['rules']
    print('## Каталог (правило CATALOG_MIN = 0,01 на построении):', ', '.join(p['catalog']), f"— {len(p['catalog'])} операторов")
    print('## Веса операторов у голов («тысячи», построение)')
    print('| голова | ' + ' | '.join(p['catalog']) + ' | остаток | «прочих» на построении |')
    print('|---|' + '---|' * (len(p['catalog']) + 2))
    for h, w in p['weights']['thousands'].items():
        print(f'| {SHORT[h]} | ' + ' | '.join(r(x, 3) for x in w['pi'][:-1]) + f" | {r(w['pi'][-1], 3)} | {w['n_other']} |")
    s5 = p['sets']['test5_thousands']['envs']
    print('## Пилот: test5 «тысячи» (уже виденные ответы; описательно)')
    print('| среда | m_M (М − Т того же размера) | m_Mo (по «прочим») | top3 | m_MT (М+Т − таблица 30) | m_T30 (М − таблица 30) |')
    print('|---|---|---|---|---|---|')
    for en in sorted(s5):
        q = s5[en]['point']
        print(f"| {en} | {r(q['m_M'], 4, True)} | {r(q['m_Mo'], 4, True)} | {r(q['top3'], 4, True)} | {r(q['m_MT'], 4, True)} | {r(q['m_T30'], 4, True)} |")
    for meas in ('m_M', 'top3', 'm_MT'):
        xs = [s5[en]['point'][meas] for en in s5]
        print(f"- {meas}: среднее по 8 средам {r(sum(xs) / len(xs), 4, True)}; больше нуля в {sum(x > 0 for x in xs)} средах из {len(xs)}")
    pw = p['power']['test5_thousands']
    print('## Мощность для 8 новых сред (модель «новая среда», пилот — test5 «тысячи») и правило активности')
    act, exp = {}, {}
    for rule, (meas, kind, part_b) in T.RULES.items():
        q = pw[meas]['power']
        dec = q['confirm'] + (q['refute'] if kind == 'two' else 0.0)
        act[rule] = dec >= POWER_MIN
        exp[rule] = dict(measure=meas, kind=kind, power=q, decisive=dec, active=act[rule], expect=round(0.95 * dec, 4),
                         expect_outcome=('меньше' if kind == 'two' and q['refute'] > q['confirm'] else 'подтверждено/больше'),
                         bits_yes=round(math.log2(max(dec, 1e-12) / LEVEL), 2), bits_no=round(math.log2((1 - min(dec, 1 - 1e-12)) / (1 - LEVEL)), 2))
        print(f"- {rule} ({meas}, {'двусторонний' if kind == 'two' else 'односторонний'}): «подтверждено/больше» {r(q['confirm'], 4)}, «опровергнуто/меньше» "
              f"{r(q['refute'], 4)}, часть А {r(q['part_a'], 4)}, часть Б {r(q['part_b'], 4)} → решающая {r(dec, 4)} → {'решающее' if act[rule] else 'описательно'}")
    for rule, kind in T.AB_RULES.items():
        src = {'prog': 'АБ-П-Т', 'shape': 'АБ-Ф-Т'}[kind]
        mp = e3[src]['power_min']
        exp[rule] = dict(kind=kind, power_min_d3=mp, active=True, expect=round(0.95 * mp, 4),
                         bits_yes=round(math.log2(mp / LEVEL), 2), bits_no=round(math.log2((1 - mp) / (1 - LEVEL)), 2))
        print(f"- {rule} (повтор DISTILL-03, {kind}): наименьшая мощность DISTILL-03 {r(mp, 3)} (общий шум — от числа сред не зависит) → ожидание «да» {r(0.95 * mp, 4)}")
    ok = T.RULES_ACTIVE is not None and all(T.RULES_ACTIVE[k] == act[k] for k in act)
    print('## Замок: test_d4.RULES_ACTIVE совпадает с правилом активности —', ok)
    if '--write' in a:
        json.dump(dict(rule='0,95 × решающая мощность пилота 2 (test5) / наименьшая мощность DISTILL-03 для A-на-B', power_min=POWER_MIN, level=LEVEL,
                       pilot='gha_out/distill04_pilot2/pilot.json', rules=exp), open(os.path.join(HERE, 'expect_d4.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('записано expect_d4.json')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
