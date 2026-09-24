#!/usr/bin/env python3
"""false_level.py — посчитать ложный уровень правила до заморозки PLAN, а не предполагать его.

  binom  <p0> <n> <k>          P(≥k успехов из n | вероятность успеха при нулевом эффекте p0)
  pairs  <file.json> <порог>   p0 из разностей всех пар значений контроля (список чисел в json) и P(≥k/n) для всех k
  perm   <a.json> <b.json> [N] перестановочный тест разницы средних двух групп (N перестановок, по умолчанию 20000)

Урок Neu (AUTO-02): разброс оценили по 3 сидам, он оказался в 4–5 раз больше; порог «2,5 SD» был на деле 0,5 SD.
Считайте p0 по пилоту или по контролю — этим скриптом — и пишите число в PLAN.
"""
import sys, json, math, random


def binom_tail(p, n, k):
    return sum(math.comb(n, m) * p ** m * (1 - p) ** (n - m) for m in range(k, n + 1))


def main():
    c = sys.argv[1] if len(sys.argv) > 1 else '-h'
    if c == 'binom':
        p, n, k = float(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
        print(f'P(≥{k}/{n} | p0={p}) = {binom_tail(p, n, k):.4g}')
    elif c == 'pairs':
        v = json.load(open(sys.argv[2])); thr = float(sys.argv[3])
        d = [a - b for i, a in enumerate(v) for j, b in enumerate(v) if i != j]
        p0 = sum(x >= thr for x in d) / len(d)
        print(f'p0 = P(разность ≥ {thr} при нулевом эффекте) = {p0:.3f}  (по {len(d)} парам контроля)')
        n = len(v)
        for k in range(1, n + 1):
            print(f'  P(≥{k}/{n}) = {binom_tail(p0, n, k):.4g}')
    elif c == 'perm':
        a, b = json.load(open(sys.argv[2])), json.load(open(sys.argv[3])); N = int(sys.argv[4]) if len(sys.argv) > 4 else 20000
        obs = sum(a) / len(a) - sum(b) / len(b); pool = a + b; rnd = random.Random(0); hit = 0
        for _ in range(N):
            rnd.shuffle(pool); x, y = pool[:len(a)], pool[len(a):]
            hit += abs(sum(x) / len(x) - sum(y) / len(y)) >= abs(obs)
        print(f'разница средних {obs:.4g}; двусторонний перестановочный p = {(hit + 1) / (N + 1):.4g}')
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
