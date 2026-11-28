# EVO-02: две головы с «профдеформацией», перенос генов, размножение и смерть (см. PREREG-EVO-02.md).
# Основа — evo01.py (язык программ, задачи, скрытая правда). Оценщик во всех ветвях — 16 свежих случайных тестов за поколение.
# Ветви: BASE | HGT (генофонд рабочих кусков) | LIFE (энергия, старение, рождение и смерть) |
#        TWO (голова A: + − ×; голова B: + − % // if; «мозолистое тело» C выбирает голову: C(x) < 0 → A, иначе B) |
#        SPLIT (как TWO, но C задан при рождении случайно и не наследуется от отбора: мутирует/скрещивается только A и B).
import sys, os, json, time
import numpy as np
import evo01 as E

POP, GENS, TOUR = E.POP, E.GENS, E.TOUR
OPS_A = {'+': 2, '-': 2, '*': 2}
OPS_B = {'+': 2, '-': 2, '%': 2, '/': 2, 'if': 4}


def rand_tree_ops(r, d, ops):
    if d <= 1 or r.random() < 0.3:
        return 'x' if r.random() < 0.5 else int(r.integers(-3, 8))
    op = list(ops)[r.integers(len(ops))]
    return (op,) + tuple(rand_tree_ops(r, d - 1, ops) for _ in range(ops[op]))


def mutate_ops(t, r, ops, pool=None):
    ps = list(E.nodes(t)); p = ps[r.integers(len(ps))]
    sub = pool[r.integers(len(pool))] if pool else rand_tree_ops(r, 3, ops)
    n = E.put(t, p, sub)
    return n if E.depth(n) <= E.MAXD else t


def out_of(org, x):
    if isinstance(org, dict):                       # двухголовый: мозолистое тело выбирает голову
        c = E.ev(org['C'], x)
        return np.where(c < 0, E.ev(org['A'], x), E.ev(org['B'], x))
    return E.ev(org, x)


def ops_in(t, ops):
    return all((not isinstance(n, tuple)) or n[0] in ops for n in (E.get(t, p) for p in E.nodes(t)))


def run(task, arm, seed):
    r = np.random.default_rng(seed * 1000 + int(task[1]))
    f = E.TASKS[task]
    hid = np.random.default_rng(10 ** 6 + seed).integers(E.LO, E.HI + 1, 1000); yhid = f(hid)
    truth = lambda o: float((out_of(o, hid) == yhid).mean())
    two = arm in ('TWO', 'SPLIT')
    new_org = (lambda: dict(A=rand_tree_ops(r, 4, OPS_A), B=rand_tree_ops(r, 4, OPS_B), C=E.rand_tree(r, 3))) if two else (lambda: E.rand_tree(r, 4))
    pop = [new_org() for _ in range(POP)]
    age = np.zeros(POP); energy = np.ones(POP)
    pool, hist = [], []
    for g in range(GENS + 1):
        X = r.integers(E.LO, E.HI + 1, 16); y = f(X)
        score = np.array([(out_of(o, X) == y).mean() for o in pop])
        best = int(np.argmax(score))
        hist.append(dict(gen=g, n=len(pop), claimed=float(score[best]), true=truth(pop[best])))
        if g == GENS: break
        pick = lambda: max(r.integers(len(pop), size=TOUR), key=lambda k: score[k])
        if arm == 'HGT':                            # генофонд: поддеревья лучших 10 %, до 300 штук
            top = np.argsort(-score)[:max(1, len(pop) // 10)]
            for i in top:
                ps = list(E.nodes(pop[i])); pool.append(E.get(pop[i], ps[r.integers(len(ps))]))
            pool = pool[-300:]
        if arm == 'LIFE':                           # энергия: +доля верных − 0,5 за поколение; смерть при энергии < 0 или возрасте > 20
            energy = energy + score - 0.5; age = age + 1
            alive = [i for i in range(len(pop)) if energy[i] >= 0 and age[i] <= 20]
            kids, kage, ken = [], [], []
            for i in alive:
                if energy[i] >= 1.0 and len(alive) + len(kids) < 2 * POP:     # размножение: половина энергии ребёнку
                    mate = alive[r.integers(len(alive))]
                    c = E.cross(pop[i], pop[mate], r)
                    if r.random() < 0.3: c = E.mutate(c, r)
                    energy[i] /= 2; kids.append(c); kage.append(0); ken.append(energy[i])
            pop = [pop[i] for i in alive] + kids
            age = np.concatenate([age[alive], kage]); energy = np.concatenate([energy[alive], ken])
            while len(pop) < POP // 6:                                        # вымирание — подселение случайных
                pop.append(new_org()); age = np.append(age, 0); energy = np.append(energy, 1.0)
            continue
        new = [pop[best]]
        while len(new) < POP:
            i = pick()
            if two:
                a = pop[i]; c = dict(a)
                if r.random() < 0.7:
                    b = pop[pick()]
                    for k in ('A', 'B') + (('C',) if arm == 'TWO' else ()):
                        c[k] = E.cross(a[k], b[k], r) if r.random() < 0.5 else a[k]
                if r.random() < 0.3:
                    k = ('A', 'B', 'C')[r.integers(3)] if arm == 'TWO' else ('A', 'B')[r.integers(2)]
                    c[k] = mutate_ops(c[k], r, OPS_A if k == 'A' else (OPS_B if k == 'B' else E.OPS))
                c['A'] = c['A'] if ops_in(c['A'], OPS_A) else a['A']          # профдеформация соблюдается и при скрещивании
                c['B'] = c['B'] if ops_in(c['B'], OPS_B) else a['B']
            else:
                c = E.cross(pop[i], pop[pick()], r) if r.random() < 0.7 else pop[i]
                if r.random() < 0.3:
                    c = mutate_ops(c, r, E.OPS, pool if (arm == 'HGT' and pool and r.random() < 0.5) else None)
            new.append(c)
        pop = new
    return dict(task=task, arm=arm, seed=seed, hist=hist, final_true=hist[-1]['true'], final_claimed=hist[-1]['claimed'])


if __name__ == '__main__':
    task, arm, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
    t0 = time.time(); res = run(task, arm, seed); res['sec'] = round(time.time() - t0, 1)
    os.makedirs('runs', exist_ok=True); json.dump(res, open(f'runs/{task}_{arm}_s{seed}.json', 'w'))
    print(task, arm, seed, 'правда', round(res['final_true'], 3), 'оценщик', round(res['final_claimed'], 3), 'n', res['hist'][-1]['n'], res['sec'], 'с')
