"""Статистика CHILD-01. Функции скопированы дословно из experiments/2026-11-27_DEFER-01/defer01.py (там проверены внесением ошибок):
точная перестановка знаков полным перебором, единица проверки — сид, бутстреп по сидам целиком."""
import numpy as np
ALPHA_SIDE = 0.005
TIE = 1e-12

# ───────── статистика ─────────
def seed_means(keys, vals):
    """Среднее по задачам внутри каждого сида: единица проверки — сид (входы у задач одного сида общие)."""
    by = {}
    for (task, seed), v in zip(keys, vals): by.setdefault(seed, []).append(v)
    seeds = sorted(by)
    return seeds, np.array([float(np.mean(by[s])) for s in seeds])

def signflip_p(m):
    """Точная проверка перестановкой знаков (полный перебор 2^n): доля раскладов знаков со средней не меньше наблюдённой."""
    m = np.asarray(m, float); n = len(m)
    assert 1 <= n <= 22, n
    obs = m.sum(); a = np.abs(m)
    sums = np.zeros(1)
    for x in a: sums = np.concatenate([sums + x, sums - x])       # все 2^n сумм
    tol = 1e-12 * max(1.0, a.sum())
    return float(np.mean(sums >= obs - tol)), float(np.mean(sums <= obs + tol))   # p «вверх», p «вниз»

def directional(keys, vals, name=''):
    """Проверка с вердиктом: предсказано, что средняя по сидам > 0."""
    seeds, m = seed_means(keys, vals)
    if len(m) < 8 or np.all(np.abs(m) < TIE):
        return dict(seeds=len(m), verdict='n мало', mean=float(np.mean(m)) if len(m) else None)
    p_up, p_down = signflip_p(m)
    verdict = 'подтверждено' if p_up <= ALPHA_SIDE else ('обратный эффект' if p_down <= ALPHA_SIDE else 'не решено')
    return dict(seeds=len(m), mean=round(float(m.mean()), 5), ci95=cluster_ci(keys, vals), p_predicted=round(p_up, 6), p_opposite=round(p_down, 6),
                seeds_positive=int(np.sum(m > TIE)), seeds_negative=int(np.sum(m < -TIE)), verdict=verdict)

def cluster_ci(keys, vals, B=4000, seed=0, stat=None):
    """Бутстреп-интервал 95 % средней (или stat) с пересэмплированием сидов целиком."""
    by = {}
    for k, v in zip(keys, vals): by.setdefault(k[1], []).append(v)
    seeds = sorted(by); r = np.random.default_rng(seed); out = []
    for _ in range(B):
        pick = r.integers(0, len(seeds), len(seeds))
        x = np.concatenate([np.asarray(by[seeds[i]], float) for i in pick])
        out.append(float(np.mean(x)) if stat is None else stat(x))
    return [round(float(np.percentile(out, 2.5)), 5), round(float(np.percentile(out, 97.5)), 5)]

def counts(vals):
    v = np.asarray(vals, float)
    return dict(pos=int(np.sum(v > TIE)), neg=int(np.sum(v < -TIE)), ties=int(np.sum(np.abs(v) <= TIE)), median=round(float(np.median(v)), 5), mean=round(float(np.mean(v)), 5))

def by_task(keys, vals):
    out = {}
    for t in sorted({k[0] for k in keys}):
        out[t] = counts([v for k, v in zip(keys, vals) if k[0] == t])
    return out

