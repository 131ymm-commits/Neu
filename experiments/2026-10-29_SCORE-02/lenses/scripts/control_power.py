# Пилот (не в зачёт): контраст AUC(agree) − AUC(single, огрублённая до распределения уровней agree этапа) и его мощность.
# Огрубление задаётся один раз на этап (края по всей выборке этапа), бутстреп задач — по огрублённым значениям.
import sys, math, random, collections
from statistics import NormalDist
sys.path.insert(0, '/tmp/claude-0/-home-claude/8c9bf095-e181-55d3-b75e-353e8e0f2d42/scratchpad/lenses_score02')
import pilot_lib as PL
Z = NormalDist().inv_cdf(0.975); PHI = NormalDist().cdf
def edges_of(agree_all):
    lv = collections.Counter(round(c, 4) for c, _ in agree_all); tot = sum(lv.values()); cum = 0; e = []
    for k in sorted(lv): cum += lv[k]; e.append(cum / tot)
    return e
def coarsen_map(single_all, e):
    vals = sorted(c for c, _ in single_all); n = len(vals); pos = {}; i = 0
    while i < n:
        j = i
        while j < n and vals[j] == vals[i]: j += 1
        pos[vals[i]] = (i + j) / 2 / n; i = j
    return lambda c: next(k for k, x in enumerate(e) if pos[c] <= x + 1e-12)
for m in ('opus', 'haiku'):
    calls = PL.load_calls(f'{PL.SP}/pilot_{m}_out.jsonl')
    J = {t: PL.judg(calls[t], PL.lab[t]) for t in sorted(calls)}
    S = [j for t in J for j in J[t]['single']]; A = [j for t in J for j in J[t]['agree']]
    f = coarsen_map(S, edges_of(A))
    Jc = {t: [(f(c), o) for c, o in J[t]['single']] for t in J}
    mu = PL.auc_fast(A) - PL.auc_fast([j for t in J for j in Jc[t]])
    rng = random.Random(4242 + len(m)); tasks = sorted(J); xs = []
    for _ in range(4000):
        smp = [rng.choice(tasks) for _ in tasks]
        xs.append(PL.auc_fast([j for t in smp for j in J[t]['agree']]) - PL.auc_fast([j for t in smp for j in Jc[t]]))
    xs.sort(); mb = sum(xs) / len(xs); sd = math.sqrt(sum((x - mb) ** 2 for x in xs) / (len(xs) - 1))
    pw = {n: (PHI(-mu / (sd * math.sqrt(20 / n)) - Z), sum(PHI(-x / (sd * math.sqrt(20 / n)) - Z) for x in xs) / len(xs)) for n in (100, 59)}
    print(f'{m}: AUC agree − AUC single огрублённой = {mu:+.4f} [{xs[100]:+.4f}; {xs[3899]:+.4f}], SD {sd:.4f}; мощность «< 0»: 100 задач {pw[100][0]:.3f}/{pw[100][1]:.3f}, 59 задач {pw[59][0]:.3f}/{pw[59][1]:.3f}')
