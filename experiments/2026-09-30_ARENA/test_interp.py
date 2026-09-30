# Сверка интерпретатора с CPython (песочница) на тестовом наборе; плюс проверка отказов и лимитов.
import random, json
from interp import run
from sandbox import run_py
CASES = [
 ("def f(p):\n    return p['a'] // p['b']", [{'a': -7, 'b': 2}, {'a': 7, 'b': -2}, {'a': -7, 'b': -2}]),
 ("def f(p):\n    return p['a'] % p['b']", [{'a': -7, 'b': 3}, {'a': 7, 'b': -3}]),
 ("def f(p):\n    a, b = 1, 2\n    a, b = b, a + b\n    return a * 10 + b", [{}]),
 ("def f(p):\n    x = [0] * p['n']\n    for i in range(p['n']):\n        x[i] = x[i - 1] + i\n    return x[-1]", [{'n': 10}, {'n': 1}]),
 ("def f(p):\n    s = 0\n    i = p['n']\n    while i > 0:\n        s += i % 10\n        i //= 10\n    return s", [{'n': 987654321}]),
 ("def g(k):\n    if k < 2:\n        return k\n    return g(k - 1) + g(k - 2)\ndef f(p):\n    return g(p['n'])", [{'n': 15}]),
 ("def f(p):\n    d = {}\n    for v in p['xs']:\n        d[v % 3] = d.get(v % 3, 0) + v\n    return sum(d.values()) * len(d)", [{'xs': [5, -4, 9, 12, 7]}]),
 ("def f(p):\n    a = sorted(p['xs'])\n    return sum(i * v for i, v in enumerate(a)) + max(a) - min(a)", [{'xs': [3, -1, 4, 1, 5, 9, 2, 6]}]),
 ("def f(p):\n    return pow(3, p['e'], 1000000007) + (2 ** 100) % 97", [{'e': 10**18}]),
 ("def f(p):\n    c = 0\n    for i in range(p['n']):\n        if i % 3 == 0:\n            continue\n        if i > 50:\n            break\n        c += i\n    else:\n        c = -1\n    return c", [{'n': 100}, {'n': 20}]),
 ("def f(p):\n    xs = list(range(10))\n    xs[2:5] = [0]\n    del xs[0]\n    return len(xs) * 100 + sum(xs[::2])", [{}]),
 ("def f(p):\n    m = [[0] * 3 for _ in range(3)]\n    m[1][2] = 5\n    return sum(sum(r) for r in m) + (7 if m[1][2] == 5 else 0)", [{}]),
]
bad = 0
for src, ps in CASES:
    for p in ps:
        a = run(src, p); b = run_py(src, p)
        ok = a[0] == 'ok' and b[0] == 'ok' and a[1] == b[1]
        bad += not ok
        if not ok: print('РАСХОЖДЕНИЕ', src.splitlines()[-1], p, a, b)
# случайные арифметические выражения
r = random.Random(1)
ops = ['+', '-', '*', '//', '%']
for _ in range(300):
    e = str(r.randint(-50, 50))
    for _ in range(r.randint(1, 5)): e = f'({e} {r.choice(ops)} {r.choice([r.randint(-9, -1), r.randint(1, 9)])})'
    src = f"def f(p):\n    return {e}"
    a = run(src, {}); b = run_py(src, {})
    if not (a[0] == b[0] == 'ok' and a[1] == b[1]): bad += 1; print('РАСХОЖДЕНИЕ', e, a, b)
# отказы и лимиты
for src, want in [("import os\ndef f(p):\n    return 1", 'reject'), ("def f(p):\n    return 7 / 2", 'reject'), ("def f(p):\n    return 1.5", 'reject'),
                  ("def f(p):\n    while True:\n        pass", 'limit'), ("def f(p):\n    return open('x')", 'reject'), ("def f(p):\n    return p.__class__", 'reject'),
                  ("def f(p):\n    return 'a'", 'error'), ("def g():\n    return g()\ndef f(p):\n    return g()", 'limit')]:
    a = run(src, {})
    if a[0] != want: bad += 1; print('ОТКАЗ НЕ ТОТ', src.splitlines()[-1], a)
print('расхождений', bad)
