# HIVE-01: вопросы на предсказание с точной правдой, где у голов ожидается устранимая ошибка (после пилота PRED-01),
# плюс контроли неустранимого шума.
import math, random, json, sys, os, itertools
import numpy as np
from pred_q import primes_in, subsets_count


def colorings3(n, edges):
    adj = [[] for _ in range(n)]
    for a, b in edges: adj[a].append(b); adj[b].append(a)
    col = [-1] * n; order = sorted(range(n), key=lambda v: -len(adj[v]))
    def dfs(i):
        if i == n: return 1
        v = order[i]; tot = 0
        for c in range(3):
            if all(col[u] != c for u in adj[v]):
                col[v] = c; tot += dfs(i + 1); col[v] = -1
        return tot
    return dfs(0)


def distinct_partitions(n):
    q = [1] + [0] * n
    for k in range(1, n + 1):
        for s in range(n, k - 1, -1): q[s] += q[s - k]
    return q[n]


def twin_pairs(a, L):
    lim = a + L + 2
    seg_primes = set()
    base = np.ones(int(math.isqrt(lim)) + 2, bool); base[:2] = False
    for i in range(2, int(len(base) ** 0.5) + 1):
        if base[i]: base[i * i::i] = False
    seg = np.ones(L + 3, bool)
    for p in np.nonzero(base)[0]:
        p = int(p); st = max(p * p, (a + p - 1) // p * p)
        seg[st - a::p] = False
    for x in range(a, min(a + L + 3, 2)): seg[x - a] = False
    return int(sum(1 for i in range(L + 1) if seg[i] and seg[i + 2]))


def collatz_steps(n):
    k = 0
    while n != 1: n = n // 2 if n % 2 == 0 else 3 * n + 1; k += 1
    return k


def _col3(r):
    n = r.randint(10, 14); m = r.randint(int(1.3 * n), int(1.8 * n))
    E = set()
    while len(E) < m:
        a, b = sorted(r.sample(range(n), 2)); E.add((a, b))
    E = sorted(E)
    es = ', '.join(f'{a + 1}–{b + 1}' for a, b in E)
    return dict(fam='COL3', kind='count', text=f'Граф на вершинах 1…{n} с рёбрами {es}. Сколько существует правильных раскрасок его вершин в 3 цвета (соседние вершины разного цвета; цвета различимы)?',
                truth=colorings3(n, E))


def make(fam, seed):
    r = random.Random(f'{fam}:{seed}')
    if fam == 'COL3':  # графы без раскрасок пропускаются (ошибка в разах для 0 не определена)
        for k in range(100):
            q = _col3(random.Random(f'{fam}:{seed}:{k}'))
            if q['truth'] > 0: return q
    if fam == 'PART':
        n = r.randint(80, 260)
        return dict(fam=fam, kind='count', text=f'Сколькими способами можно представить число {n} в виде суммы различных натуральных слагаемых (порядок не важен)?', truth=distinct_partitions(n))
    if fam == 'TWIN':
        a = r.randint(10 ** 7, 10 ** 9); L = r.choice([10 ** 5, 3 * 10 ** 5, 10 ** 6])
        return dict(fam=fam, kind='count', text=f'Сколько пар простых чисел-близнецов (p, p + 2) с p в отрезке от {a} до {a + L}?', truth=twin_pairs(a, L))
    if fam == 'SUB5':
        M = r.randint(25, 40); S = r.randint(5 * M // 3, 5 * M * 2 // 3)
        return dict(fam=fam, kind='count', text=f'Сколько существует 5-элементных подмножеств множества {{1, 2, …, {M}}} с суммой элементов ровно {S}?', truth=subsets_count(M, 5, S))
    if fam == 'COLLATZ':  # контроль: неустранимый хаос
        n = r.randint(10 ** 11, 10 ** 13)
        return dict(fam=fam, kind='count', text=f'Сколько шагов нужно последовательности Коллатца (n → n/2 для чётного, n → 3n + 1 для нечётного), чтобы из {n} дойти до 1?', truth=collatz_steps(n))
    raise ValueError(fam)


FAMS = ['COL3', 'PART', 'TWIN', 'SUB5', 'COLLATZ']

if __name__ == '__main__':
    tag, seed0, per = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    qs = []
    for f in FAMS:
        for i in range(per):
            q = make(f, seed0 + i); q['id'] = f'{f}-{seed0 + i}'; qs.append(q)
            print(q['id'], q['truth'])
    os.makedirs(tag, exist_ok=True)
    json.dump(qs, open(f'{tag}/questions.json', 'w'), ensure_ascii=False, indent=1)
