# Проверяльщик SCORE-01, линза 3: мощность по пилоту двумя способами бутстрепом.
#  «в точке» — тест из 100 задач, выбранных с возвращением из пилотных (истина = пилот как есть);
#  «с неопределённостью пилота» — сначала пилот пересэмплируется по задачам (истина неизвестна), потом тест из 100.
# Устройство теста как в черновике: Opus — один вызов на клетку (WIN−LOG — пара одного повтора; NONE — с повтором 1 рук LOG и WIN),
# Haiku — среднее двух вызовов (в пилоте LOG и WIN — два повтора, NONE — один). Вердикт — t-интервал, как analyze_score01.
import json, math, sys
import numpy as np
from scipy import stats
SC = '/home/claude/neu/experiments/2026-10-28_SCORE-01'
sys.path.insert(0, SC)
from analyze_score01 import PRED
rng = np.random.default_rng(20261029)
def val(r, m): return r['conf'] - r['acc'] if m == 'self_dec' else (float(r['out']) if m == 'out' else r[m])
def w_of(tg):
    if tg[0] == 'pair': return {tg[1]: 1.0, tg[2]: -1.0}
    if tg[0] == 'arm': return {tg[1]: 1.0}
    return dict(tg[1])
def cell_matrix(model):
    """Для каждой пилотной задачи — варианты значений всех предсказаний модели (по варианту на «вызов теста»)."""
    R = json.load(open(f'{SC}/evals/pilot12_{model}.json'))['rows']; T = sorted({r['task'] for r in R.values()})
    ps = [p for p in PRED if p['model'] == model]
    per_task = []
    for t in T:
        if model == 'opus':
            variants = []
            for k in ('0', '1'):          # вариант теста: руки LOG, WIN — повтор k; NONE — повтор 0 (пилот 2)
                row = []
                for p in ps:
                    w = w_of(p['target']); m = p['measure']
                    if 'NONE' in w:       # с NONE — только повтор 1 рук LOG, WIN (тот же прогон)
                        row.append(sum(wa * val(R[f'{t}|{a}|{"0" if a == "NONE" else "1"}'], m) for a, wa in w.items()))
                    else:
                        row.append(sum(wa * val(R[f'{t}|{a}|{k}'], m) for a, wa in w.items()))
                variants.append(row)
        else:
            row = []
            for p in ps:
                w = w_of(p['target']); m = p['measure']
                v = {a: np.mean([val(R[f'{t}|{a}|{k}'], m) for k in '01' if f'{t}|{a}|{k}' in R]) for a in w}
                row.append(sum(wa * v[a] for a, wa in w.items()))
            variants = [row]
        per_task.append(np.array(variants))
    return ps, per_task
def verdict(x, p):
    n = len(x); m = x.mean(); s = x.std(ddof=1)
    if p['kind'] == 'equiv':
        h = stats.t.ppf(0.95, n - 1) * s / math.sqrt(n); return (m - h > -p['margin']) and (m + h < p['margin'])
    h = stats.t.ppf(0.975, n - 1) * s / math.sqrt(n)
    return (m + h < 0) if p['kind'] == 'lt0' else (m - h > 0)
def sim(model, B=4000, n=100, outer=True):
    ps, per_task = cell_matrix(model); K = len(per_task)
    comps = sorted({p['comp'] for p in ps if p['comp']})
    hits = np.zeros(len(ps)); chits = {c: 0 for c in comps}
    for b in range(B):
        base = rng.integers(0, K, K) if outer else np.arange(K)        # пилот пересэмплирован (неопределённость) или как есть
        idx = base[rng.integers(0, K, n)]
        X = np.array([per_task[i][rng.integers(0, len(per_task[i]))] for i in idx])
        ok = [verdict(X[:, j], p) for j, p in enumerate(ps)]
        hits += ok
        for c in comps:
            chits[c] += all(ok[j] for j, p in enumerate(ps) if p['comp'] == c)
    return {p['id']: hits[j] / B for j, p in enumerate(ps)}, {c: v / B for c, v in chits.items()}
PW = json.load(open(f'{SC}/pilot_power.json'))
for model in ('opus', 'haiku'):
    a_pt, c_pt = sim(model, outer=False); a_un, c_un = sim(model, outer=True)
    print(f'== {model}: мощность (нормальное приближение черновика) | бутстреп в точке | с неопределённостью пилота')
    for pid in a_pt:
        print(f'  {pid:4s} {PW[pid]["power"]:.3f} | {a_pt[pid]:.3f} | {a_un[pid]:.3f}')
    for c in c_pt:
        parts = [p['id'] for p in PRED if p['comp'] == c]
        prod = math.prod(PW[i]['power'] for i in parts)
        print(f'  сводный {c}: произведение {prod:.3f} | совместно в точке {c_pt[c]:.3f} | совместно с неопределённостью {c_un[c]:.3f}')
