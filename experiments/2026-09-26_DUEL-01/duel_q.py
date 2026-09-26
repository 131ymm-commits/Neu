# DUEL-01: задачи, которые составляют сами головы, выбирая параметры в известных семействах. Правду считает код.
# Семейства и ограничения размеров (чтобы правда считалась за секунды):
#   COL3  — граф: n ≤ 16 вершин, ≤ 40 рёбер; вопрос — число правильных 3-раскрасок (≥ 1).
#   PART  — n от 20 до 400; число разбиений на различные слагаемые.
#   TWIN  — отрезок [a, a + L], 10^6 ≤ a ≤ 10^10, 10^3 ≤ L ≤ 10^6; число пар близнецов с p в отрезке.
#   SUB   — k от 3 до 7, M от 15 до 50, сумма S; число k-подмножеств {1..M} с суммой S (≥ 1).
import json, math
from hive_q import colorings3, distinct_partitions, twin_pairs
from pred_q import subsets_count

LIMITS = ('COL3: n ≤ 16 вершин, не больше 40 рёбер, вершины 1…n, у графа должна быть хотя бы одна раскраска; '
          'PART: n от 20 до 400; TWIN: a от 1000000 до 10000000000, длина L от 1000 до 1000000; '
          'SUB: k от 3 до 7, M от 15 до 50, сумма S такая, что подходящих подмножеств хотя бы одно.')


def text(fam, p):
    if fam == 'COL3':
        return f'Граф на вершинах 1…{p["n"]} с рёбрами ' + ', '.join(f'{a}–{b}' for a, b in p['edges']) + '. Сколько существует правильных раскрасок его вершин в 3 цвета (соседние вершины разного цвета; цвета различимы)?'
    if fam == 'PART':
        return f'Сколькими способами можно представить число {p["n"]} в виде суммы различных натуральных слагаемых (порядок не важен)?'
    if fam == 'TWIN':
        return f'Сколько пар простых чисел-близнецов (p, p + 2) с p в отрезке от {p["a"]} до {p["a"] + p["L"]}?'
    if fam == 'SUB':
        return f'Сколько существует {p["k"]}-элементных подмножеств множества {{1, 2, …, {p["M"]}}} с суммой элементов ровно {p["S"]}?'
    raise ValueError(fam)


def validate(fam, p):
    """-> (нормализованные параметры, None) или (None, причина отказа)."""
    try:
        I = lambda x: int(x) if (isinstance(x, (int, float)) and not isinstance(x, bool) and float(x).is_integer()) else None
        if fam == 'COL3':
            n = I(p['n']); E = sorted({tuple(sorted((I(a), I(b)))) for a, b in p['edges']})
            if n is None or not 3 <= n <= 16: return None, 'n вне 3…16'
            if len(E) > 40 or any(a is None or b is None or a == b or not (1 <= a <= n and 1 <= b <= n) for a, b in E): return None, 'рёбра'
            return dict(n=n, edges=[list(e) for e in E]), None
        if fam == 'PART':
            n = I(p['n']); return (dict(n=n), None) if n is not None and 20 <= n <= 400 else (None, 'n вне 20…400')
        if fam == 'TWIN':
            a, L = I(p['a']), I(p['L'])
            return (dict(a=a, L=L), None) if a is not None and L is not None and 10 ** 6 <= a <= 10 ** 10 and 10 ** 3 <= L <= 10 ** 6 else (None, 'a или L вне пределов')
        if fam == 'SUB':
            k, M, S = I(p['k']), I(p['M']), I(p['S'])
            return (dict(k=k, M=M, S=S), None) if None not in (k, M, S) and 3 <= k <= 7 and 15 <= M <= 50 and 1 <= S <= k * M else (None, 'k, M или S вне пределов')
    except Exception as e:
        return None, f'формат: {type(e).__name__}'
    return None, 'семейство'


def truth(fam, p):
    if fam == 'COL3': return colorings3(p['n'], [(a - 1, b - 1) for a, b in p['edges']])
    if fam == 'PART': return distinct_partitions(p['n'])
    if fam == 'TWIN': return twin_pairs(p['a'], p['L'])
    if fam == 'SUB': return subsets_count(p['M'], p['k'], p['S'])


if __name__ == '__main__':
    import time
    for fam, p in [('COL3', dict(n=16, edges=[[i, i + 1] for i in range(1, 16)] + [[1, 16], [1, 8], [3, 12]])), ('PART', dict(n=400)),
                   ('TWIN', dict(a=9_999_000_000, L=1_000_000)), ('SUB', dict(k=7, M=50, S=180))]:
        q, err = validate(fam, p); t0 = time.time(); v = truth(fam, q); print(fam, v, f'{time.time() - t0:.2f} с', text(fam, q)[:80])
