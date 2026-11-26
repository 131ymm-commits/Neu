#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04 «ПРОЧИЕ» (HYPOTHESIS.md, 11ae9f8c): разведка, описательно, до PREREG. Какие операторы f(a, b) строят неверные ответы
голов, которые не объясняются потерей переноса («прочие» ошибки DISTILL-02). Данные — построение (OCDIV-03/04) и уже виденные
test5/new5 DISTILL-02; тест DISTILL-04 будет на новых ответах. Решений здесь нет: итог — каталог операторов для PREREG.
  «прочий» ответ — числовой ответ y ≠ s (s = a + b), чьё смещение y − s не равно −Σ 10^j по набору разрядов с переносом (distill02.lost_set).
  Операторы (кандидаты неверного ответа; ответ может подходить под несколько):
    plus10j    — s + 10^j (лишний перенос, «+1 в разряде»), j = 0 … len(s);
    minus10j   — s − 10^j в разряде без переноса («−1 в разряде»; с переносом — это потеря переноса);
    digit_pm1  — одна цифра суммы ±1 по модулю 10, без переноса в соседний разряд;
    shift      — сдвиг слагаемого на разряд: a + 10b, a + ⌊b/10⌋, 10a + b, ⌊a/10⌋ + b;
    operand    — ответ равен слагаемому: a или b;
    omit_digit — пропущена одна цифра суммы; dup_digit — одна цифра суммы повторена; transpose — переставлены соседние цифры суммы;
    concat     — слагаемые записаны подряд: «ab» или «ba»;
    drop_b_digit, drop_a_digit — цифра слагаемого пропущена: s − d_j·10^j (вторая разведка, после −20…−90 в первой);
    move_b_digit, move_a_digit — цифра слагаемого учтена в соседнем разряде: s − d_j·10^j + d_j·10^(j±1).
  Для наборов теста DISTILL-02 — ещё покрытие таблицей: доля «прочих» ответов, чьё смещение входит в 30 самых частых «прочих»
  смещений головы на построении того же семейства (как q программы DISTILL-02).
  python3 explore_d4.py ВЫХОД.json SPEC.json
SPEC: {"construction": {семейство: [папки]}, "sets": {имя: {"family": семейство, "dirs": [папки]}}}"""
import json
import os
import sys
import time

import numpy as np

X_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X_DIR))
sys.path.insert(0, os.path.join(ROOT, 'experiments', '2026-11-18_DISTILL-02'))
import distill02 as D2  # noqa: E402

NC = D2.NC
TOP = D2.TOP_OFFSETS
OPS = ('plus10j', 'minus10j', 'digit_pm1', 'shift', 'operand', 'omit_digit', 'dup_digit', 'transpose', 'concat',
       'drop_b_digit', 'drop_a_digit', 'move_b_digit', 'move_a_digit')   # вторая разведка: после −20…−90 в первой (a2b5306e)


def carry_positions(a, b):
    return [r['j'] for r in D2.position_features(a, b, 0)]


def candidates(a, b):
    """{оператор: множество неверных ответов ≥ 0, ≠ s}."""
    s = a + b
    st = str(s)
    n = len(st)
    cpos = set(carry_positions(a, b))
    c = {}
    c['plus10j'] = {s + 10 ** j for j in range(n + 1)}
    c['minus10j'] = {s - 10 ** j for j in range(n) if j not in cpos and s - 10 ** j >= 0}
    dp = set()
    for i, ch in enumerate(st):
        for dd in (1, -1):
            t = st[:i] + str((int(ch) + dd) % 10) + st[i + 1:]
            if t[0] != '0' or len(t) == 1:
                dp.add(int(t))
    c['digit_pm1'] = dp
    c['shift'] = {a + 10 * b, a + b // 10, 10 * a + b, a // 10 + b}
    c['operand'] = {a, b}
    c['omit_digit'] = {int(st[:i] + st[i + 1:]) for i in range(n)} if n > 1 else set()
    c['dup_digit'] = {int(st[:i] + st[i] + st[i:]) for i in range(n)}
    c['transpose'] = {int(st[:i] + st[i + 1] + st[i] + st[i + 2:]) for i in range(n - 1) if not (i == 0 and st[1] == '0')}
    c['concat'] = {int(str(a) + str(b)), int(str(b) + str(a))}
    # вторая разведка: цифра слагаемого пропущена (s − d_j·10^j) или учтена не в своём разряде (s − d_j·10^j + d_j·10^(j±1))
    for name, x in (('b', b), ('a', a)):
        dg = [int(ch) for ch in reversed(str(x))]
        c[f'drop_{name}_digit'] = {s - d * 10 ** j for j, d in enumerate(dg) if d}
        c[f'move_{name}_digit'] = {s - d * 10 ** j + d * 10 ** k for j, d in enumerate(dg) if d for k in (j - 1, j + 1) if k >= 0}
    return {k: {y for y in v if y != s and y >= 0} for k, v in c.items()}


def classify(it, d):
    """Смещение ответа → 'correct' | 'lost' | 'other' (числовые); None — нечисловой ответ."""
    if d >= NC:
        return None
    if d == 0:
        return 'correct'
    return 'lost' if D2.lost_set(int(d), carry_positions(it['a'], it['b'])) is not None else 'other'


def head_stats(items, offs, table=None):
    """Счёт по одной голове: классы ответов, покрытие «прочих» операторами и таблицей (если дана)."""
    cnt = dict(numeric=0, correct=0, lost=0, other=0)
    by_op = {k: 0 for k in OPS}
    union, by_table = 0, 0
    only = {k: 0 for k in OPS}                     # «прочие», которые объясняет ровно этот оператор
    unexplained = {}
    examples = {}
    other_offsets = {}
    for it, d in zip(items, offs):
        c = classify(it, d)
        if c is None:
            continue
        cnt['numeric'] += 1
        cnt[c] += 1
        if c != 'other':
            continue
        y = it['sum'] + int(d)
        other_offsets[int(d)] = other_offsets.get(int(d), 0) + 1
        cand = candidates(it['a'], it['b'])
        hit = [k for k in OPS if y in cand[k]]
        for k in hit:
            by_op[k] += 1
        if len(hit) == 1:
            only[hit[0]] += 1
        if hit:
            union += 1
        else:
            unexplained[int(d)] = unexplained.get(int(d), 0) + 1
            ex = examples.setdefault(int(d), [])
            if len(ex) < 8:
                ex.append((it['a'], it['b'], it['sum'], y))
        if table is not None and int(d) in table:
            by_table += 1
    no = max(cnt['other'], 1)
    out = dict(cnt, share_other=cnt['other'] / max(cnt['numeric'], 1),
               by_op={k: dict(n=v, share=v / no) for k, v in by_op.items()},
               only_op={k: v for k, v in only.items()},
               union=dict(n=union, share=union / no),
               unexplained_top=sorted(unexplained.items(), key=lambda kv: -kv[1])[:15],
               unexplained_examples={d: examples[d] for d, _ in sorted(unexplained.items(), key=lambda kv: -kv[1])[:3]},
               other_top=sorted(other_offsets.items(), key=lambda kv: -kv[1])[:TOP])
    if table is not None:
        out['table'] = dict(n=by_table, share=by_table / no)
    return out


def load_sets(dirs, fam):
    envs = []
    for d in dirs:
        envs += [(n, e) for n, e in D2.load_merged(d).items() if D2.family_of(n) == fam]
    return envs


def pooled(envs):
    """Задачи и смещения по головам из списка сред (голова — только если есть во всех средах, как D2.family_data)."""
    return D2.family_data([e for _, e in envs])


def main(a):
    t0 = time.time()
    dst, spec = a[0], json.load(open(a[1], encoding='utf-8'))
    out = dict(ops=list(OPS), top=TOP, construction={}, sets={})
    tables = {}
    for fam, dirs in spec['construction'].items():
        items, offs = pooled(load_sets(dirs, fam))
        out['construction'][fam] = {}
        tables[fam] = {}
        for h, o in sorted(offs.items()):
            st = head_stats(items, o)
            out['construction'][fam][h] = st
            tables[fam][h] = {d for d, _ in st['other_top']}            # 30 самых частых «прочих» смещений, как q программы
    for name, s in spec.get('sets', {}).items():
        fam = s['family']
        items, offs = pooled(load_sets(s['dirs'], fam))
        out['sets'][name] = {h: head_stats(items, o, tables.get(fam, {}).get(h)) for h, o in sorted(offs.items())}
    out['seconds'] = round(time.time() - t0, 1)
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for part, d in (('построение', out['construction']), ('наборы', out['sets'])):
        for k, heads in d.items():
            for h, st in heads.items():
                print(part, k, h, '| «прочих»', st['other'], f"({st['share_other']:.3f} числовых)", '| объяснено операторами',
                      f"{st['union']['share']:.3f}", ('| таблицей ' + f"{st['table']['share']:.3f}") if 'table' in st else '', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
