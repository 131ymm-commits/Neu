#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCGEO-01: тесты до регистрации.
1. ocgeo_extract_test.py отличается от pilot1/ocgeo_extract.py ровно одной строкой SPLIT = 'test'.
2. Разбиение задач: пилот и тест не пересекаются, вместе — все 8098 пар (без двух пар подсказки); пилот 30 %.
3. Пары подсказки совпадают с подсказкой пилота 0 (зерно 7 190 000).
4. Число задач OOD теста = n_test_ood в power.json."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FAIL = []


def check(c, msg):
    print(('  ✓ ' if c else '  ✗ ') + msg)
    if not c:
        FAIL.append(msg)


a = open(os.path.join(HERE, 'pilot1', 'ocgeo_extract.py'), encoding='utf-8').read().splitlines()
b = open(os.path.join(HERE, 'ocgeo_extract_test.py'), encoding='utf-8').read().splitlines()
diff = [(x, y) for x, y in zip(a, b) if x != y]
check(len(a) == len(b) and len(diff) == 1 and diff[0][1].startswith("SPLIT = 'test'"), f'извлечение теста отличается одной строкой: {diff}')
g = np.random.default_rng(7_190_000)
ex = [(int(g.integers(10, 100)), int(g.integers(10, 100))) for _ in range(2)] + [(int(g.integers(100, 1000)), int(g.integers(100, 1000))) for _ in range(2)]
check(set(ex[:2]) == {(67, 68), (56, 67)}, f'пары подсказки: {ex[:2]}')
pairs = [(x, y) for x in range(10, 100) for y in range(10, 100) if (x, y) not in set(ex)]
perm = np.random.default_rng(7_200_000).permutation(len(pairs))
n_p = int(round(0.3 * len(pairs)))
pil, tst = set(perm[:n_p].tolist()), set(perm[n_p:].tolist())
check(len(pairs) == 8098 and not (pil & tst) and len(pil | tst) == 8098 and len(pil) == 2429, f'разбиение: пилот {len(pil)}, тест {len(tst)}, без пересечений')
d = json.load(open(os.path.join(HERE, 'pilot1', 'out', 'answers.json'), encoding='utf-8'))
check(sorted(p['id'] for p in d['problems']) == sorted(pil), 'задачи пилота 1 = часть «пилот» разбиения')
pw = json.load(open(os.path.join(HERE, 'power.json'), encoding='utf-8'))
n_ood = sum(pairs[i][0] + pairs[i][1] >= 100 for i in tst)
check(pw['n_test_ood'] == n_ood, f'задач OOD в тесте: {n_ood} (power.json: {pw["n_test_ood"]})')
print('ПРОВАЛОВ:', len(FAIL))
sys.exit(1 if FAIL else 0)
