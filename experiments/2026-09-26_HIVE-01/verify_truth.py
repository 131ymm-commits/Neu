# HIVE-01: правда вторыми способами (решение совета, заседание 5).
import itertools, random
from hive_q import distinct_partitions, colorings3, twin_pairs, collatz_steps
from pred_q import subsets_count

def odd_parts(n):
    p = [1] + [0] * n
    for k in range(1, n + 1, 2):
        for s in range(k, n + 1): p[s] += p[s - k]
    return p[n]

assert all(distinct_partitions(n) == odd_parts(n) for n in range(300)); print('PART: q(n) = разбиения на нечётные (Эйлер), n < 300')
for s in range(25):
    r = random.Random(s); n = r.randint(6, 10); E = sorted({tuple(sorted(r.sample(range(n), 2))) for _ in range(int(1.6 * n))})
    assert sum(1 for c in itertools.product(range(3), repeat=n) if all(c[a] != c[b] for a, b in E)) == colorings3(n, E)
print('COL3: поиск с возвратом = прямой перебор, 25 графов')
for k, v in [(3, 35), (4, 205), (5, 1224), (6, 8169), (7, 58980)]:  # π2(10^k), OEIS A007508 (по памяти)
    assert twin_pairs(1, 10 ** k - 1) == v
print('TWIN: π2(10^k) для k = 3…7 совпадает с опубликованными значениями (по памяти)')
for s in range(10):
    r = random.Random(s); M = r.randint(15, 30); S = r.randint(20, 5 * M - 10)
    assert subsets_count(M, 5, S) == sum(1 for c in itertools.combinations(range(1, M + 1), 5) if sum(c) == S)
print('SUB5: динамика = прямой перебор, 10 случаев')
assert collatz_steps(27) == 111 and collatz_steps(97) == 118
print('COLLATZ: целевая величина — число шагов до первого достижения 1 (27 → 111, 97 → 118)')
