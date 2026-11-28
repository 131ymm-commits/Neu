# EVO-03: три проверки с общей мерой ИОИ (truth.py), см. PREREG-EVO-03.md.
#  A. MIRROR_f: зеркальный зоопарк тестов с притоком новизны — доля f из 8 новых тестов берётся свежей случайной (f = 0, 0.25, 0.5, 1).
#  B. Две головы там, где задача устроена как «две профессии», и там, где нет (TWO против BASE).
#  C. LIFE2: размножение и смерть с относительной ценой жизни (энергия += доля верных − средняя по популяции).
import sys, os, json, time
import numpy as np
import evo01 as E
import evo02 as E2
from truth import ioi

E.TASKS.update({
    'T4': lambda x: np.where(x < 0, x * x + 1, x % 6),       # «две профессии»: арифметика слева, остаток справа
    'T5': lambda x: np.where(x < 10, 3 * x - 2, x // 4),      # «две профессии»: линейная слева, деление справа
    'T6': lambda x: x * x * x - x,                            # только арифметика
})


def run_mirror(task, f_new, seed):
    r = np.random.default_rng(seed * 1000 + int(task[1])); f = E.TASKS[task]
    hid = np.random.default_rng(10 ** 6 + seed).integers(E.LO, E.HI + 1, 1000); yhid = f(hid)
    pop = [E.rand_tree(r, 4) for _ in range(E.POP)]; hist = []
    mt = r.integers(E.LO, E.HI + 1, 16); tscore = None
    for g in range(E.GENS + 1):
        if g > 0:
            order = np.argsort(-tscore); keep = mt[order[:8]]
            kids = np.clip(keep + r.integers(-5, 6, 8), E.LO, E.HI)
            fresh = r.random(8) < f_new
            kids[fresh] = r.integers(E.LO, E.HI + 1, int(fresh.sum()))
            mt = np.concatenate([keep, kids])
        okm = np.array([E.ev(t, mt) == f(mt) for t in pop]); score = okm.mean(1)
        pp = okm.mean(0); tscore = pp * (1 - pp) + r.random(16) * 1e-9
        best = int(np.argmax(score))
        hist.append(dict(gen=g, claimed=float(score[best]), true=float((E.ev(pop[best], hid) == yhid).mean())))
        if g == E.GENS: break
        new = [pop[best]]
        while len(new) < E.POP:
            i = max(r.integers(E.POP, size=E.TOUR), key=lambda k: score[k])
            c = E.cross(pop[i], pop[max(r.integers(E.POP, size=E.TOUR), key=lambda k: score[k])], r) if r.random() < 0.7 else pop[i]
            if r.random() < 0.3: c = E.mutate(c, r)
            new.append(c)
        pop = new
    return hist


def run_life2(task, seed):
    # Пилот 1 (сид 999) показал обвал численности: одновременное старение когорты и нет рождений при нулевых ответах.
    # Версия 2 (зарегистрирована): у каждой особи своя продолжительность жизни (геометрическая, в среднем 20 поколений);
    # смерть — по возрасту или при энергии < −0,5; освободившиеся места заполняют потомки, родители выбираются
    # пропорционально энергии (сдвинутой к положительной), партнёр — тоже. Численность постоянна (300).
    r = np.random.default_rng(seed * 1000 + int(task[1])); f = E.TASKS[task]
    hid = np.random.default_rng(10 ** 6 + seed).integers(E.LO, E.HI + 1, 1000); yhid = f(hid)
    N = E.POP
    pop = [E.rand_tree(r, 4) for _ in range(N)]
    life = r.geometric(1 / 20, N); age = np.zeros(N); energy = np.zeros(N); hist = []
    for g in range(E.GENS + 1):
        X = r.integers(E.LO, E.HI + 1, 16); y = f(X)
        score = np.array([(E.ev(t, X) == y).mean() for t in pop]); best = int(np.argmax(score))
        hist.append(dict(gen=g, n=len(pop), deaths=None, claimed=float(score[best]), true=float((E.ev(pop[best], hid) == yhid).mean())))
        if g == E.GENS: break
        energy = energy + score - score.mean(); age = age + 1
        dead = (age > life) | (energy < -0.5)
        hist[-1]['deaths'] = int(dead.sum())
        alive = np.where(~dead)[0]
        if len(alive) == 0: alive = np.array([best])
        w = energy[alive] - energy[alive].min() + 1e-3; w = w / w.sum()
        kids = []
        for _ in range(N - len(alive)):
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
    if arm.startswith('MIRROR'):
        hist = run_mirror(task, int(arm.split('_')[1]) / 100, seed)
    elif arm == 'LIFE2':
        hist = run_life2(task, seed)
    else:                                                          # BASE, TWO — из EVO-02 без изменений
        hist = E2.run(task, arm, seed)['hist']
    res = dict(task=task, arm=arm, seed=seed, hist=hist, **ioi(hist), final_true=hist[-1]['true'], sec=round(time.time() - t0, 1))
    os.makedirs('runs', exist_ok=True); json.dump(res, open(f'runs/{task}_{arm}_s{seed}.json', 'w'))
    print(task, arm, seed, 'ИОИ', round(res['ioi'], 3), 'правда', round(res['final_true'], 3), 'n', hist[-1].get('n'), res['sec'], 'с')
