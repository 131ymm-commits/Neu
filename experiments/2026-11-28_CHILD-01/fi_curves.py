"""CHILD-01: функциональная информация (Szostak 2003; Hazen и др. 2007) в мире EVO.
I(x) = −log2 F(x), где F(x) — доля программ (по мере случайного порождения rand_tree глубины D), у которых правда не ниже x.
Правда здесь — доля верных ответов на всей области входов (201 целое от −100 до 100).
Два способа: (1) прямое моделирование — пока F не слишком мала; (2) расщепление по уровням (subset simulation) с блужданием по деревьям,
сохраняющим меру порождения, — для редких уровней. Нижняя граница для F(1) — сумма вероятностей нескольких известных точных решений.
  python3 fi_curves.py direct <задача> <D> <число образцов> <сид>
  python3 fi_curves.py split  <задача> <D> <N частиц> <шагов> <сид>
  python3 fi_curves.py all    — всё по плану, пишет fi_curves.json"""
import sys, os, json, math, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import evo03 as E3
from evo03 import E
X = np.arange(E.LO, E.HI + 1); NX = len(X)                       # вся область входов: 201 точка
OPS = list(E.OPS)


def level(t, Y):                                                  # число верных ответов из 201
    return int((E.ev(t, X) == Y).sum())


def logp(t, d):
    """Логарифм вероятности породить дерево t вызовом rand_tree(r, d)."""
    leaf = not isinstance(t, tuple)
    if d <= 1: return (math.log(0.5) if t == 'x' else math.log(0.5 / 11)) if leaf else -math.inf
    if leaf: return math.log(0.3) + (math.log(0.5) if t == 'x' else math.log(0.5 / 11))
    return math.log(0.7 / 6) + sum(logp(c, d - 1) for c in t[1:])


def nodes_d(t, d, path=()):
    yield path, d
    if isinstance(t, tuple):
        for i, c in enumerate(t[1:], 1): yield from nodes_d(c, d - 1, path + (i,))


def propose(t, D, r):
    """Перегенерировать случайно выбранное поддерево из меры порождения. Возвращает (новое дерево, n_old, n_new)."""
    ps = list(nodes_d(t, D)); p, d = ps[r.integers(len(ps))]
    n = E.put(t, p, E.rand_tree(r, d))
    return n, len(ps), sum(1 for _ in E.nodes(n))


def direct(task, D, M, seed):
    r = np.random.default_rng(seed); Y = E.TASKS[task](X); h = np.zeros(NX + 1, int)
    for _ in range(M): h[level(E.rand_tree(r, D), Y)] += 1
    return h


def split(task, D, N, steps, seed, p0=0.2):
    """Расщепление по уровням. Возвращает log2 F(k) для k = 0…201 (None, где уровень не достигнут)."""
    r = np.random.default_rng(seed); Y = E.TASKS[task](X)
    pop = [E.rand_tree(r, D) for _ in range(N)]; lv = np.array([level(t, Y) for t in pop])
    logF = np.full(NX + 1, np.nan); cur, lf_cur = 0, 0.0               # текущий порог и log2 F(порог)
    while True:
        tail = np.array([(lv >= k).mean() for k in range(NX + 1)])      # условные доли при пороге cur
        for k in range(cur, NX + 1):
            if tail[k] > 0 and np.isnan(logF[k]): logF[k] = lf_cur + math.log2(tail[k])
        cand = [k for k in range(cur + 1, NX + 1) if 0 < tail[k] <= p0]
        if not cand:
            if tail[NX] > 0 or lv.max() <= cur: break                   # дошли до верха или дальше образцов нет
            nxt = int(lv.max())
        else: nxt = cand[0]
        if tail[nxt] * N < 5 and nxt < NX and (lv >= nxt).sum() < 5: break   # слишком мало затравок — дальше оценка ненадёжна
        seeds = [i for i in range(N) if lv[i] >= nxt]
        lf_cur += math.log2(len(seeds) / N); cur = nxt
        new, nlv = [], []
        for j in range(N):                                              # цепи из затравок, блуждание при условии уровень ≥ cur
            i = seeds[j % len(seeds)]; t, l = pop[i], lv[i]
            for _ in range(steps):
                c, n0, n1 = propose(t, D, r)
                if r.random() < n0 / n1:
                    lc = level(c, Y)
                    if lc >= cur: t, l = c, lc
            new.append(t); nlv.append(l)
        pop, lv = new, np.array(nlv)
        if cur == NX: 
            logF[NX] = lf_cur; break
    return [None if np.isnan(x) else round(float(x), 3) for x in logF]


def _job(j):
    return direct(j[1], j[2], j[3], j[4]).tolist() if j[0] == 'direct' else split(j[1], j[2], j[3], j[4], j[5])


SOLUTIONS = {   # известные точные решения — для нижней границы F(1)
    'T1': [('+', ('*', 'x', ('-', 'x', 3)), 7), ('+', 7, ('*', 'x', ('-', 'x', 3))), ('+', ('*', ('-', 'x', 3), 'x'), 7), ('+', 7, ('*', ('-', 'x', 3), 'x')),
           ('+', ('*', 'x', ('+', 'x', -3)), 7), ('+', ('*', 'x', ('+', -3, 'x')), 7), ('+', 7, ('*', 'x', ('+', 'x', -3))), ('+', 7, ('*', 'x', ('+', -3, 'x')))],
    'T2': [('if', 0, 'x', ('%', 'x', 7), ('-', 0, 'x')), ('if', 'x', 1, ('-', 0, 'x'), ('%', 'x', 7)), ('if', 'x', 0, ('-', 0, 'x'), ('%', 'x', 7)),
           ('if', -1, 'x', ('%', 'x', 7), ('-', 0, 'x')), ('if', 0, 'x', ('%', 'x', 7), ('*', 'x', -1)), ('if', 'x', 1, ('*', 'x', -1), ('%', 'x', 7)),
           ('if', 0, 'x', ('%', 'x', 7), ('*', -1, 'x')), ('if', 'x', 1, ('*', -1, 'x'), ('%', 'x', 7))],
    'T3': [('+', ('*', ('/', 'x', 3), 2), ('%', 'x', 5)), ('+', ('%', 'x', 5), ('*', ('/', 'x', 3), 2)), ('+', ('*', 2, ('/', 'x', 3)), ('%', 'x', 5)),
           ('+', ('%', 'x', 5), ('*', 2, ('/', 'x', 3)))],
    'T4': [('if', 'x', 0, ('+', ('*', 'x', 'x'), 1), ('%', 'x', 6)), ('if', 'x', 0, ('+', 1, ('*', 'x', 'x')), ('%', 'x', 6)),
           ('if', -1, 'x', ('%', 'x', 6), ('+', ('*', 'x', 'x'), 1)), ('if', -1, 'x', ('%', 'x', 6), ('+', 1, ('*', 'x', 'x')))],
    'T5': [('if', 'x', ('+', 3, 7), ('-', ('*', 3, 'x'), 2), ('/', 'x', 4)), ('if', 'x', ('+', 5, 5), ('-', ('*', 3, 'x'), 2), ('/', 'x', 4)),
           ('if', 'x', ('+', 7, 3), ('-', ('*', 'x', 3), 2), ('/', 'x', 4)), ('if', 'x', ('*', 2, 5), ('-', ('*', 3, 'x'), 2), ('/', 'x', 4))],
    'T6': [('*', 'x', ('-', ('*', 'x', 'x'), 1)), ('*', ('-', ('*', 'x', 'x'), 1), 'x'), ('-', ('*', 'x', ('*', 'x', 'x')), 'x'), ('-', ('*', ('*', 'x', 'x'), 'x'), 'x')],
}


def lower_bound(task, D):
    Y = E.TASKS[task](X); tot = 0.0
    for t in SOLUTIONS[task]:
        assert level(t, Y) == NX, (task, t, level(t, Y))                # решение обязано быть точным на всей области
        tot += math.exp(logp(t, D))
    return math.log2(tot)


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'direct':
        task, D, M, seed = sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
        print(json.dumps(dict(task=task, D=D, M=M, seed=seed, hist=direct(task, D, M, seed).tolist())))
    elif mode == 'split':
        task, D, N, steps, seed = sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
        print(json.dumps(dict(task=task, D=D, N=N, steps=steps, seed=seed, logF=split(task, D, N, steps, seed))))
    elif mode == 'bound':
        for t in sorted(SOLUTIONS): print(t, {D: round(lower_bound(t, D), 2) for D in (4, 6)})
    elif mode == 'all':
        from concurrent.futures import ProcessPoolExecutor
        jobs = [('direct', t, D, 1_500_000, 7) for t in sorted(SOLUTIONS) for D in (6, 4)] + \
               [('split', t, D, 2000, 8, s) for t in sorted(SOLUTIONS) for D in (6, 4) for s in (1, 2, 3, 4)]
        def fmt(j): return j
        out = dict(note='log2 F(k): доля программ с числом верных ответов не меньше k из 201; мера — rand_tree глубины D', X=NX, direct={}, split={}, bound={})
        with ProcessPoolExecutor(max_workers=4) as ex:
            res = list(ex.map(_job, jobs))
        for j, v in zip(jobs, res):
            if j[0] == 'direct':
                h = np.array(v); tail = h[::-1].cumsum()[::-1] / h.sum()
                out['direct'][f'{j[1]}_D{j[2]}'] = dict(M=int(h.sum()), logF=[None if x == 0 else round(float(math.log2(x)), 3) for x in tail], max_level=int(np.nonzero(h)[0].max()))
            else:
                out['split'].setdefault(f'{j[1]}_D{j[2]}', []).append(v)
        for t in sorted(SOLUTIONS): out['bound'][t] = {f'D{D}': round(lower_bound(t, D), 3) for D in (6, 4)}
        json.dump(out, open(os.path.join(HERE, 'fi_curves.json'), 'w'))
        print('готово')
