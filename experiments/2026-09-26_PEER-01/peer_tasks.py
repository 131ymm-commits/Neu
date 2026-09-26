# PEER-01: математико-логические задачи, у которых либо нет решений, либо их много.
# У каждой задачи — полный перебор (сколько решений) и проверщик любого предложенного решения.
# Семейства: NUM (четыре числа), SQ (квадрат 3×3), COL (раскраска графа), DIO (целые решения системы).
import itertools, json, random, sys

# ---------------------------------------------------------------- NUM
def num_text(p):
    return (f'Найдите четыре различных натуральных числа a < b < c < d, каждое не больше {p["M"]}, такие что '
            f'a + b + c + d = {p["S"]} и a² + b² + c² + d² = {p["Q"]}. Решение — список [a, b, c, d].')

def num_all(p):
    return [list(t) for t in itertools.combinations(range(1, p['M'] + 1), 4) if sum(t) == p['S'] and sum(x * x for x in t) == p['Q']]

def num_check(p, s):
    return (isinstance(s, list) and len(s) == 4 and all(isinstance(x, int) and not isinstance(x, bool) for x in s)
            and s == sorted(set(s)) and 1 <= s[0] and s[-1] <= p['M'] and sum(s) == p['S'] and sum(x * x for x in s) == p['Q'])

def num_gen(r):
    M = r.randint(20, 40)
    t = sorted(r.sample(range(1, M + 1), 4))
    S, Q = sum(t), sum(x * x for x in t)
    Q += r.choice([0, 0, 1, 2, -2])  # сдвиг чётности/значения может сделать задачу нерешаемой
    return dict(M=M, S=S, Q=Q)

# ---------------------------------------------------------------- SQ
def sq_text(p):
    return (f'Расставьте числа 1, 2, …, 9 (каждое ровно один раз) в квадрат 3×3 так, чтобы суммы строк сверху вниз были '
            f'{p["rows"][0]}, {p["rows"][1]}, {p["rows"][2]}, суммы столбцов слева направо — {p["cols"][0]}, {p["cols"][1]}, {p["cols"][2]}, '
            f'а сумма чисел на главной диагонали (слева сверху вправо вниз) была {p["diag"]}. '
            'Решение — список из трёх строк, например [[1, 2, 3], [4, 5, 6], [7, 8, 9]].')

def sq_all(p):
    out = []
    for perm in itertools.permutations(range(1, 10)):
        g = [perm[0:3], perm[3:6], perm[6:9]]
        if [sum(x) for x in g] != p['rows']: continue
        if [g[0][j] + g[1][j] + g[2][j] for j in range(3)] != p['cols']: continue
        if g[0][0] + g[1][1] + g[2][2] != p['diag']: continue
        out.append([list(x) for x in g])
    return out

def sq_check(p, s):
    try:
        flat = [x for row in s for x in row]
        if len(s) != 3 or any(len(row) != 3 for row in s) or sorted(flat) != list(range(1, 10)) or any(isinstance(x, bool) for x in flat): return False
        return ([sum(x) for x in s] == p['rows'] and [s[0][j] + s[1][j] + s[2][j] for j in range(3)] == p['cols']
                and s[0][0] + s[1][1] + s[2][2] == p['diag'])
    except Exception:
        return False

def sq_gen(r):
    perm = r.sample(range(1, 10), 9); g = [perm[0:3], perm[3:6], perm[6:9]]
    rows = [sum(x) for x in g]; cols = [g[0][j] + g[1][j] + g[2][j] for j in range(3)]; diag = g[0][0] + g[1][1] + g[2][2]
    k = r.random()
    if k < 0.35:  # перенос единицы между строками (суммы остаются 45)
        i, j = r.sample(range(3), 2); rows[i] += 1; rows[j] -= 1
    elif k < 0.5:
        diag += r.choice([-3, -2, 2, 3])
    return dict(rows=rows, cols=cols, diag=diag)

# ---------------------------------------------------------------- COL
def col_text(p):
    e = ', '.join(f'{a}–{b}' for a, b in p['edges'])
    return (f'Граф: вершины 1…{p["n"]}, рёбра {e}. Раскрасьте вершины в {p["k"]} цвета (цвета 1…{p["k"]}) так, чтобы концы каждого ребра '
            f'были разного цвета, и при этом вершина 1 имела цвет 1, а вершина 2 — цвет 2. Решение — список цветов вершин 1…{p["n"]} по порядку.')

def col_all(p):
    out = []
    for c in itertools.product(range(1, p['k'] + 1), repeat=p['n']):
        if c[0] != 1 or c[1] != 2: continue
        if all(c[a - 1] != c[b - 1] for a, b in p['edges']): out.append(list(c))
    return out

def col_check(p, s):
    return (isinstance(s, list) and len(s) == p['n'] and all(isinstance(x, int) and not isinstance(x, bool) and 1 <= x <= p['k'] for x in s)
            and s[0] == 1 and s[1] == 2 and all(s[a - 1] != s[b - 1] for a, b in p['edges']))

def col_gen(r):
    n = r.randint(10, 12)
    m = r.randint(int(1.9 * n), int(2.3 * n))
    edges = set()
    while len(edges) < m:
        a, b = sorted(r.sample(range(1, n + 1), 2)); edges.add((a, b))
    return dict(n=n, k=3, edges=sorted(edges))

# ---------------------------------------------------------------- DIO
def dio_text(p):
    return (f'Найдите целые x, y, z, каждое от {-p["B"]} до {p["B"]}, такие что x + y + z = {p["s"]} и x² + y² − z² = {p["t"]}, '
            f'причём x < y. Решение — список [x, y, z].')

def dio_all(p):
    B = p['B']; out = []
    for x in range(-B, B + 1):
        for y in range(x + 1, B + 1):
            z = p['s'] - x - y
            if -B <= z <= B and x * x + y * y - z * z == p['t']: out.append([x, y, z])
    return out

def dio_check(p, s):
    return (isinstance(s, list) and len(s) == 3 and all(isinstance(v, int) and not isinstance(v, bool) and -p['B'] <= v <= p['B'] for v in s)
            and s[0] < s[1] and sum(s) == p['s'] and s[0] ** 2 + s[1] ** 2 - s[2] ** 2 == p['t'])

def dio_gen(r):
    B = r.choice([20, 30, 40])
    return dict(B=B, s=r.randint(-15, 15), t=r.randint(-60, 60))

FAM = dict(NUM=(num_gen, num_text, num_all, num_check), SQ=(sq_gen, sq_text, sq_all, sq_check),
           COL=(col_gen, col_text, col_all, col_check), DIO=(dio_gen, dio_text, dio_all, dio_check))
MANY = 5  # «много решений» — не меньше 5


def shallow(fam, p):
    """Невозможность видна простым признаком (после пилота 1: такие задачи головы решают сразу) — такие не берём."""
    if fam == 'NUM':
        return (p['S'] - p['Q']) % 2 != 0 or p['S'] < 10 or p['S'] > 4 * p['M'] - 6
    if fam == 'SQ':
        return (not all(6 <= x <= 24 for x in p['rows'] + p['cols'] + [p['diag']]) or sum(p['rows']) != 45 or sum(p['cols']) != 45)
    if fam == 'COL':
        adj = {v: set() for v in range(1, p['n'] + 1)}
        for a, b in p['edges']: adj[a].add(b); adj[b].add(a)
        return any(all(y in adj[x] for x, y in itertools.combinations(q, 2)) for q in itertools.combinations(range(1, p['n'] + 1), 4))
    if fam == 'DIO':
        return (p['s'] - p['t']) % 2 != 0
    return False


def make(fam, want, seed):
    """want: 'none' (0 решений) или 'many' (>= MANY). Перебор параметров детерминирован."""
    gen, text, allf, _ = FAM[fam]
    for k in range(4000):
        r = random.Random(f'{fam}:{want}:{seed}:{k}')
        p = gen(r)
        n = len(allf(p))
        if shallow(fam, p): continue
        if (want == 'none' and n == 0) or (want == 'many' and MANY <= n <= 30):
            return dict(id=f'{fam}-{want}-{seed}', fam=fam, want=want, seed=seed, params=p, text=text(p), n_solutions=n)
    raise RuntimeError((fam, want, seed))


def check(task, sol):
    return FAM[task['fam']][3](task['params'], sol)


if __name__ == '__main__':
    import time
    for fam in FAM:
        for want in ('none', 'many'):
            t0 = time.time(); t = make(fam, want, 900)
            ok = [check(t, s) for s in FAM[fam][2](t['params'])[:50]]
            print(fam, want, t['n_solutions'], all(ok), f'{time.time() - t0:.1f} с', t['text'][:120])
