# Мощность «подтверждено в обеих» с неопределённостью пилота: E_b[Φ_main(μ_b)·Φ_rep(μ_b)] (μ общий для двух выборок)
# против E_b[Φ_main]·E_b[Φ_rep] (как в power_score02.py). Бутстреп задач пилота — свой (Python random), B = 4000.
import sys, math, random
from statistics import NormalDist
sys.path.insert(0, '/tmp/claude-0/-home-claude/8c9bf095-e181-55d3-b75e-353e8e0f2d42/scratchpad/lenses_score02')
import pilot_lib as PL
Z = NormalDist().inv_cdf(0.975); PHI = NormalDist().cdf
SP = [('SA_opus', 'opus', 'auc2', 'agree', 'single', -1), ('SB_opus', 'opus', 'self_dec', 'agree', 'single', +1),
      ('SC_opus', 'opus', 'acc', 'agree', 'single', +1), ('SD_opus', 'opus', 'self_dec', 'mean', 'single', -1),
      ('SB_haiku', 'haiku', 'self_dec', 'agree', 'single', +1), ('SC_haiku', 'haiku', 'acc', 'agree', 'single', +1),
      ('SD_haiku', 'haiku', 'self_dec', 'mean', 'single', -1)]
cache = {}
for m in ('opus', 'haiku'):
    calls = PL.load_calls(f'{PL.SP}/pilot_{m}_out.jsonl')
    J = {t: PL.judg(calls[t], PL.lab[t]) for t in sorted(calls)}
    M = {s: PL.meas([j for t in J for j in J[t][s]], fast=True) for s in ('single', 'mean', 'agree')}
    rng = random.Random(777 + len(m)); tasks = sorted(J); bsM = []
    for _ in range(4000):
        smp = [rng.choice(tasks) for _ in tasks]
        bsM.append({s: PL.meas([j for t in smp for j in J[t][s]], fast=True) for s in ('single', 'mean', 'agree')})
    cache[m] = (M, bsM)
for name, m, me, a, b, d in SP:
    M, bsM = cache[m]
    mu = M[a][me] - M[b][me]; xs = [x[a][me] - x[b][me] for x in bsM]
    mb = sum(xs) / len(xs); sd = math.sqrt(sum((x - mb) ** 2 for x in xs) / (len(xs) - 1))
    se = {n: sd * math.sqrt(20 / n) for n in (100, 59)}
    pw = lambda x, n: PHI(d * x / se[n] - Z)
    point = pw(mu, 100) * pw(mu, 59)
    prod_of_means = (sum(pw(x, 100) for x in xs) / len(xs)) * (sum(pw(x, 59) for x in xs) / len(xs))
    mean_of_prod = sum(pw(x, 100) * pw(x, 59) for x in xs) / len(xs)
    P_draft = min(point, prod_of_means, 0.999); P_joint = min(point, mean_of_prod, 0.999)
    b = lambda P: (math.log2(P / 0.025), math.log2(max(1 - P, 0.001) / 0.975))
    print(f'{name:9s} точка {point:.3f}; произв. средних {prod_of_means:.3f}; среднее произв. {mean_of_prod:.3f} → '
          f'бит (черновик) {b(P_draft)[0]:+.2f}/{b(P_draft)[1]:+.2f}; (среднее произв.) {b(P_joint)[0]:+.2f}/{b(P_joint)[1]:+.2f}')
