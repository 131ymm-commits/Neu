# EVO-04: пульсирующая кормовая база (см. PREREG-EVO-04.md). Экология — как LIFE2 (EVO-03), но ёмкость среды K(g)
# попеременно высокая (изобилие: места заполняют потомки, проверяются почти все стратегии) и низкая (голод: при сжатии
# остаются K_lo особей с наибольшей энергией, накопленной за изобилие). Средняя численность = 300, как у BASE и LIFE2.
import sys, os, json, time
import numpy as np
import evo03 as E3
from evo03 import E
from truth import ioi

K_HI, K_LO = 540, 60


def run_pulse(task, seed, phase):
    r = np.random.default_rng(seed * 1000 + int(task[1])); f = E.TASKS[task]
    hid = np.random.default_rng(10 ** 6 + seed).integers(E.LO, E.HI + 1, 1000); yhid = f(hid)
    cap = lambda g: K_HI if (g // phase) % 2 == 0 else K_LO
    N = cap(0)
    pop = [E.rand_tree(r, 4) for _ in range(N)]
    life = r.geometric(1 / 20, N); age = np.zeros(N); energy = np.zeros(N); hist = []
    for g in range(E.GENS + 1):
        X = r.integers(E.LO, E.HI + 1, 16); y = f(X)
        score = np.array([(E.ev(t, X) == y).mean() for t in pop]); best = int(np.argmax(score))
        hist.append(dict(gen=g, n=len(pop), claimed=float(score[best]), true=float((E.ev(pop[best], hid) == yhid).mean())))
        if g == E.GENS: break
        energy = energy + score - score.mean(); age = age + 1
        alive = np.where(~((age > life) | (energy < -0.5)))[0]
        if len(alive) == 0: alive = np.array([best])
        K = cap(g + 1)
        if len(alive) > K:                                              # сжатие: голод оставляет самых «сытых»
            alive = alive[np.argsort(-energy[alive])[:K]]
        w = energy[alive] - energy[alive].min() + 1e-3; w = w / w.sum()
        kids = []
        for _ in range(K - len(alive)):                                 # изобилие: места заполняют потомки
            i, j = r.choice(alive, 2, p=w)
            c = E.cross(pop[i], pop[j], r) if r.random() < 0.7 else pop[i]
            if r.random() < 0.3: c = E.mutate(c, r)
            kids.append(c)
        pop = [pop[i] for i in alive] + kids
        age = np.concatenate([age[alive], np.zeros(len(kids))])
        energy = np.concatenate([energy[alive], np.zeros(len(kids))])
        life = np.concatenate([life[alive], r.geometric(1 / 20, len(kids))])
    return hist


if __name__ == '__main__':
    task, arm, seed = sys.argv[1], sys.argv[2], int(sys.argv[3]); t0 = time.time()
    if arm.startswith('PULSE'):
        hist = run_pulse(task, seed, int(arm[5:]))
    elif arm == 'LIFE2':
        hist = E3.run_life2(task, seed)
    else:
        hist = E3.E2.run(task, arm, seed)['hist']
    res = dict(task=task, arm=arm, seed=seed, hist=hist, **ioi(hist), final_true=hist[-1]['true'],
               mean_n=float(np.mean([h.get('n', E.POP) for h in hist])), sec=round(time.time() - t0, 1))
    os.makedirs('runs', exist_ok=True); json.dump(res, open(f'runs/{task}_{arm}_s{seed}.json', 'w'))
    print(task, arm, seed, 'ИОИ', round(res['ioi'], 3), 'правда', round(res['final_true'], 3), 'ср. численность', round(res['mean_n']), res['sec'], 'с')
