"""DEFER-01, пост-хок (записано после просмотра данных; вердикты A, B, C не меняет).
Проверка замечаний арбитра третьего цикла (docs/2026-11-27_deferred_selection_critique/c3_arbiter_part2.md) своим кодом,
без функций defer01.py: чтение файлов, окна и счёт написаны заново.
  python3 posthoc.py → posthoc.json"""
import glob, json, math, os, re
from itertools import combinations
import numpy as np

H = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(H, '..')
EARLY, LATE = range(11, 41), range(121, 151)          # поколения включительно, как в PREREG §2
TIE = 1e-12

def read(folder, arm):
    """{(задача, сид): (C, T)} — массивы по поколениям 0..150."""
    out = {}
    for f in sorted(glob.glob(os.path.join(EXP, folder, 'runs', '*.json'))):
        m = re.fullmatch(r'(T\d+)_(.+)_s(\d+)\.json', os.path.basename(f))
        if not m or m.group(2) != arm: continue
        h = json.load(open(f))['hist']
        assert len(h) == 151 and [x['gen'] for x in h] == list(range(151)), f
        out[(m.group(1), int(m.group(3)))] = (np.array([x['claimed'] for x in h], float), np.array([x['true'] for x in h], float))
    return out

def mean(v, gens): return float(np.mean([v[g] for g in gens]))

def binom_two_sided(k, n):
    """Точная двусторонняя проверка знаков: вероятность раскладов не более вероятных, чем наблюдённый, при p = 1/2."""
    pk = [math.comb(n, i) / 2 ** n for i in range(n + 1)]
    return float(sum(p for p in pk if p <= pk[k] * (1 + 1e-12)))

def wilson(k, n, z=1.959964):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]

R = {}

# ── 1. Дозы EVO-03: позднее завышение W и поздняя правда по прогонам ──
ARMS = ('MIRROR_0', 'MIRROR_25', 'MIRROR_50', 'MIRROR_100')
D = {a: read('2026-09-26_EVO-03', a) for a in ARMS}
assert all(len(D[a]) == 60 for a in ARMS)
W = {a: {k: mean(D[a][k][0] - D[a][k][1], LATE) for k in D[a]} for a in ARMS}
TL = {a: {k: mean(D[a][k][1], LATE) for k in D[a]} for a in ARMS}
seeds = sorted({k[1] for k in D['MIRROR_0']})
assert len(seeds) == 20

# ставка B2: на T1 завышение у MIRROR_0 ниже, чем у MIRROR_25
d = [W['MIRROR_0'][('T1', s)] - W['MIRROR_25'][('T1', s)] for s in seeds]
R['B2_T1_pairs'] = dict(for_bet=int(sum(x < -TIE for x in d)), against_bet=int(sum(x > TIE for x in d)), ties=int(sum(abs(x) <= TIE for x in d)),
                        note='за ставку — сиды, где W(MIRROR_0) < W(MIRROR_25)')

# T2: падает ли завышение там, где задачу не решили
uns = {a: [s for s in seeds if TL[a][('T2', s)] < 0.999] for a in ARMS}
R['T2_unsolved_runs'] = {a: dict(n=len(uns[a]), W_mean=round(float(np.mean([W[a][('T2', s)] for s in uns[a]])), 3) if uns[a] else None) for a in ARMS}
both = [s for s in seeds if s in uns['MIRROR_0'] and s in uns['MIRROR_25']]
dd = [W['MIRROR_0'][('T2', s)] - W['MIRROR_25'][('T2', s)] for s in both]
R['T2_unsolved_at_M0_and_M25'] = dict(seeds=len(both), lower_at_M25=int(sum(x > TIE for x in dd)), higher_at_M25=int(sum(x < -TIE for x in dd)),
                                      diff_min=round(min(dd), 2), diff_max=round(max(dd), 2), mean=round(float(np.mean(dd)), 3),
                                      p_sign_two_sided=round(binom_two_sided(int(sum(x > TIE for x in dd)), len(dd)), 4),
                                      note='подвыборка задана исходом (нерешённые) — это не проверка причины')

# T2, средняя доза против наибольшей (пост-хок)
sol = {a: {s for s in seeds if TL[a][('T2', s)] > 0.999} for a in ARMS}
only50, only100 = len(sol['MIRROR_50'] - sol['MIRROR_100']), len(sol['MIRROR_100'] - sol['MIRROR_50'])
dw = [W['MIRROR_100'][('T2', s)] - W['MIRROR_50'][('T2', s)] for s in seeds]
hi, lo = int(sum(x > TIE for x in dw)), int(sum(x < -TIE for x in dw))
pairs_adjacent, pairs_all = 3 * 3 * 2, len(list(combinations(ARMS, 2))) * 3 * 2          # пары доз × задачи × меры (решённость, завышение)
p_sol, p_w = binom_two_sided(only50, only50 + only100), binom_two_sided(hi, hi + lo)
R['T2_M50_vs_M100'] = dict(solved_only_M50=only50, solved_only_M100=only100, solved_both=len(sol['MIRROR_50'] & sol['MIRROR_100']),
                           p_solved_two_sided=round(p_sol, 4), W_higher_at_M100=hi, W_lower_at_M100=lo, W_ties=20 - hi - lo, p_W_two_sided=round(p_w, 3),
                           comparisons_adjacent_pairs=pairs_adjacent, comparisons_all_pairs=pairs_all,
                           p_solved_bonferroni=[round(min(1, p_sol * pairs_adjacent), 2), round(min(1, p_sol * pairs_all), 2)])

# ── 2. Постоянные тесты: доля правды в приросте заявки — сумма против типичного прогона ──
for name, folder, arm, n in (('FIXED16', '2026-09-26_EVO-01', 'FIXED16', 60), ('FIXED32', '2026-09-27_EVO-06', 'FIXED32', 120)):
    X = read(folder, arm); assert len(X) == n, (name, len(X))
    keys = sorted(X)
    dC = np.array([mean(X[k][0], LATE) - mean(X[k][0], EARLY) for k in keys]); dT = np.array([mean(X[k][1], LATE) - mean(X[k][1], EARLY) for k in keys])
    gapL = np.array([mean(X[k][0] - X[k][1], LATE) for k in keys]); dG = dC - dT
    solved = np.array([mean(X[k][1], LATE) > 0.999 for k in keys])
    up = dC > TIE                                                       # прогоны, где заявка выросла
    share = dT[up] / dC[up]
    top5 = np.sort(dT)[::-1][:5]
    # ранний прирост (от поколения 0 до раннего окна) — для сравнения по прогонам, а не по суммам
    dC0 = np.array([mean(X[k][0], EARLY) - X[k][0][0] for k in keys]); dT0 = np.array([mean(X[k][1], EARLY) - X[k][1][0] for k in keys])
    up0 = dC0 > TIE; share0 = dT0[up0] / dC0[up0]
    bo = up & up0; sl, se = dT[bo] / dC[bo], dT0[bo] / dC0[bo]
    big = up & (dC > 0.02)                                              # без прогонов с ничтожным приростом заявки
    by = {}
    for i, k in enumerate(keys): by.setdefault(k[1], []).append(i)
    sds = sorted(by); r = np.random.default_rng(0); bs = []
    for _ in range(4000):                                               # отношение сумм, бутстреп по сидам целиком
        ix = np.concatenate([by[sds[j]] for j in r.integers(0, len(sds), len(sds))]); bs.append(float(dT[ix].sum() / dC[ix].sum()))
    R[name] = dict(runs=n, claim_rose=int(up.sum()), share_of_sums=round(float(dT.sum() / dC.sum()), 3),
                   median_share_per_run=round(float(np.median(share)), 2), runs_share_below_half=int(np.sum(share < 0.5)),
                   top5_runs_share_of_truth_gain=round(float(top5.sum() / dT.sum()), 2), top5_solved=int(np.sum(solved[np.argsort(dT)[::-1][:5]])),
                   top5_late_truth=[round(mean(X[keys[i]][1], LATE), 3) for i in np.argsort(dT)[::-1][:5]],
                   solved_by_late=int(solved.sum()), share_of_sums_without_solved=round(float(dT[~solved].sum() / dC[~solved].sum()), 2),
                   gap_growth_mean=round(float(dG.mean()), 3), late_gap_mean=round(float(gapL.mean()), 3),
                   gap_growth_over_late_gap=round(float(dG.mean() / gapL.mean()), 2),
                   gap_grew=int(np.sum(dG > TIE)), gap_fell=int(np.sum(dG < -TIE)), changed=int(np.sum(np.abs(dG) > TIE)),
                   share_of_sums_ci95=[round(float(np.percentile(bs, 2.5)), 2), round(float(np.percentile(bs, 97.5)), 2)],
                   claim_rose_over_002=int(big.sum()), median_share_per_run_over_002=round(float(np.median(dT[big] / dC[big])), 2),
                   runs_share_below_half_over_002=int(np.sum(dT[big] / dC[big] < 0.5)),
                   median_claim_gain=round(float(np.median(dC[up])), 3), median_truth_gain=round(float(np.median(dT[up])), 3),
                   early_claim_rose=int(up0.sum()), median_early_share_per_run=round(float(np.median(share0)), 2),
                   runs_late_less_true_than_early=int(np.sum(sl < se - TIE)), runs_late_more_true_than_early=int(np.sum(sl > se + TIE)),
                   runs_with_both_gains=int(bo.sum()),
                   p_late_vs_early_two_sided=round(binom_two_sided(int(np.sum(sl < se - TIE)), int(np.sum(sl < se - TIE)) + int(np.sum(sl > se + TIE))), 2))

# ── 3. Калибровка 11 ставок: интервал доли сбывшихся ──
F = json.load(open(os.path.join(H, 'facts.json')))['bets_summary']
R['bets'] = dict(n=F['n'], came_true=F['came_true'], share=round(F['came_true'] / F['n'], 2), wilson95=wilson(F['came_true'], F['n']),
                 mean_probability_rounded=round(F['mean_probability'], 1),
                 note='ставки зависимы (A, B, C — одни прогоны; B3, B4 почти заданы устройством ветви): вывода о недо- или переуверенности нет')

json.dump(R, open(os.path.join(H, 'posthoc.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(R, ensure_ascii=False, indent=1))
