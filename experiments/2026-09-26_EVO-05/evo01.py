# EVO-01: эволюционирующий зоопарк программ; меняется только оценщик (см. PREREG-EVO-01.md).
# Ветви оценщика: FIXED16, RANDOM16, RANDOM64, COEVO16 (16 спорных из 64 свежих), MIRROR16 (зеркальный зоопарк 16 тестов,
# эволюционирующих на спорность; ≤ 16 новых ответов за поколение), ORACLE (все 1000 скрытых — верхняя граница).
# Программа — дерево выражения над целыми: x, константы −3…7, + − × //(безопасно) %(безопасно), ifless(a,b,c,d) = c если a<b иначе d.
# Настоящее качество — доля точных ответов на 1000 скрытых входах. Отбор — только по оценщику.
import sys, json, time
import numpy as np

LO, HI, CLIP = -100, 100, 10 ** 6
TASKS = {
    'T1': lambda x: x * x - 3 * x + 7,
    'T2': lambda x: np.where(x > 0, x % 7, -x),
    'T3': lambda x: (x // 3) * 2 + (x % 5),
}
OPS = {'+': 2, '-': 2, '*': 2, '/': 2, '%': 2, 'if': 4}
POP, GENS, MAXD, TOUR = 300, 150, 6, 5


def rand_tree(r, d):
    if d <= 1 or r.random() < 0.3:
        return 'x' if r.random() < 0.5 else int(r.integers(-3, 8))
    op = list(OPS)[r.integers(len(OPS))]
    return (op,) + tuple(rand_tree(r, d - 1) for _ in range(OPS[op]))


def ev(t, x):
    if t == 'x':
        return x
    if not isinstance(t, tuple):
        return np.full_like(x, t)
    a = [ev(c, x) for c in t[1:]]
    op = t[0]
    if op == '+': v = a[0] + a[1]
    elif op == '-': v = a[0] - a[1]
    elif op == '*': v = a[0] * a[1]
    elif op == '/': v = np.where(a[1] == 0, 0, a[0] // np.where(a[1] == 0, 1, a[1]))
    elif op == '%': v = np.where(a[1] == 0, 0, a[0] % np.where(a[1] == 0, 1, a[1]))
    else: v = np.where(a[0] < a[1], a[2], a[3])
    return np.clip(v, -CLIP, CLIP)


def nodes(t, path=()):
    yield path
    if isinstance(t, tuple):
        for i, c in enumerate(t[1:], 1):
            yield from nodes(c, path + (i,))


def get(t, p):
    for i in p: t = t[i]
    return t


def put(t, p, s):
    if not p: return s
    return t[:p[0]] + (put(t[p[0]], p[1:], s),) + t[p[0] + 1:]


def depth(t):
    return 1 + max((depth(c) for c in t[1:]), default=0) if isinstance(t, tuple) else 1


def mutate(t, r):
    ps = list(nodes(t)); p = ps[r.integers(len(ps))]
    n = put(t, p, rand_tree(r, 3))
    return n if depth(n) <= MAXD else t


def cross(a, b, r):
    pa = list(nodes(a)); pb = list(nodes(b))
    n = put(a, pa[r.integers(len(pa))], get(b, pb[r.integers(len(pb))]))
    return n if depth(n) <= MAXD else a


def run(task, arm, seed):
    # одно и то же начальное зерно для всех оценщиков одного (задача, сид) — парное сравнение; hash() не используется (он случаен между запусками)
    r = np.random.default_rng(seed * 1000 + int(task[1]))
    f = TASKS[task]
    hid = np.random.default_rng(10 ** 6 + seed).integers(LO, HI + 1, 1000)     # скрытые входы (правда)
    yhid = f(hid)
    fixed = np.random.default_rng(2 * 10 ** 6 + seed).integers(LO, HI + 1, 16)
    pop = [rand_tree(r, 4) for _ in range(POP)]
    truth = lambda t: float((ev(t, hid) == yhid).mean())
    hist, labels = [], 0
    for g in range(GENS + 1):
        if arm == 'FIXED16': X = fixed; labels = 16
        elif arm == 'RANDOM16': X = r.integers(LO, HI + 1, 16); labels += 16
        elif arm == 'RANDOM64': X = r.integers(LO, HI + 1, 64); labels += 64
        elif arm == 'ORACLE': X = hid; labels = 1000
        elif arm == 'MIRROR16':                                                  # зеркальный зоопарк тестов: 16 генов-тестов
            if g == 0:
                mt = r.integers(LO, HI + 1, 16); labels += 16
            else:                                                                # тесты с малой спорностью заменяются мутантами спорных
                order = np.argsort(-tscore); keep = mt[order[:8]]
                kids = np.clip(keep + r.integers(-5, 6, 8), LO, HI)
                fresh = r.random(8) < 0.25
                kids[fresh] = r.integers(LO, HI + 1, int(fresh.sum()))
                mt = np.concatenate([keep, kids]); labels += 8
            X = mt
        else:                                                                    # COEVO16: 16 самых спорных из 64
            C = r.integers(LO, HI + 1, 64); labels += 64
            ok = np.array([ev(t, C) == f(C) for t in pop])                        # (POP, 64)
            p = ok.mean(0); sc = p * (1 - p) + r.random(64) * 1e-9
            X = C[np.argsort(-sc)[:16]]
        y = f(X)
        okm = np.array([ev(t, X) == y for t in pop])
        score = okm.mean(1)
        if arm == 'MIRROR16':
            pp = okm.mean(0); tscore = pp * (1 - pp) + r.random(len(X)) * 1e-9  # приспособленность теста — спорность
        best = int(np.argmax(score))
        hist.append(dict(gen=g, claimed=float(score[best]), true=truth(pop[best]), pop_true_mean=None if g % 50 else float(np.mean([truth(t) for t in pop]))))
        if g == GENS: break
        new = [pop[best]]                                                        # элитизм: лучший по оценщику
        while len(new) < POP:
            i = max(r.integers(POP, size=TOUR), key=lambda k: score[k])
            if r.random() < 0.7:
                j = max(r.integers(POP, size=TOUR), key=lambda k: score[k]); c = cross(pop[i], pop[j], r)
            else:
                c = pop[i]
            if r.random() < 0.3: c = mutate(c, r)
            new.append(c)
        pop = new
    return dict(task=task, arm=arm, seed=seed, labels=labels, hist=hist, final_true=hist[-1]['true'], final_claimed=hist[-1]['claimed'])


if __name__ == '__main__':
    task, arm, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
    t0 = time.time(); res = run(task, arm, seed); res['sec'] = round(time.time() - t0, 1)
    import os; os.makedirs('runs', exist_ok=True)
    json.dump(res, open(f'runs/{task}_{arm}_s{seed}.json', 'w'))
    print(task, arm, seed, 'правда', round(res['final_true'], 3), 'оценщик', round(res['final_claimed'], 3), res['sec'], 'с')
