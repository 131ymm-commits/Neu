"""DEFER-01: слепая сверка модели М3 («отсрочка отбора») с уже сохранёнными прогонами EVO-01, EVO-03, EVO-06.
Вызовов голов нет. Скрипт читает только hist[g].claimed (C) и hist[g].true (T) из json прогонов.
  python3 defer01.py selftest — проверка логики на синтетике с точным ответом (ловит сдвиг окна, знак, ничьи)
  python3 defer01.py pilot    — пилотные сиды 996–998 (DEFER-01/pilot) и пилот EVO-06 (996, 997): динамика и проверка кода
  python3 defer01.py test     — основная сверка (только после регистрации PREREG-DEFER-01.md); пишет defer01_results.json
Версия 3 — после трёх линз и замечаний математика (docs/2026-11-27_deferred_selection_critique/c2_lenses.md, c2_math.md)
и после пилота на сидах 996–998: предсказания с вердиктом заданы по задачам, единица проверки — сид."""
import glob, itertools, json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(HERE, '..')
ALPHA_SIDE = 0.005                              # на каждую сторону каждой проверки с вердиктом
EARLY, LATE = (11, 40), (121, 150)              # окна поколений включительно, как в EVO-06 §7.5
GENS = 150
TIE = 1e-12                                     # |разность| меньше этого — ничья
DOSES = (('MIRROR_0', 0.0), ('MIRROR_25', 0.125), ('MIRROR_50', 0.25), ('MIRROR_100', 0.5))   # q = f/2: доля свежих в наборе

# ───────── чтение ─────────
def load(folder, arm, gens=GENS, expect=None):
    """{(задача, сид): (C, T)}; проверяет длину hist и отсутствие NaN; expect = (число задач, число сидов на задачу)."""
    runs = {}
    for f in sorted(glob.glob(os.path.join(folder, f'T*_{arm}_s*.json'))):
        name = os.path.basename(f)[:-5]
        task, rest = name.split('_', 1)
        head, _, tail = rest.rpartition('_s')
        if head != arm or not tail.isdigit(): continue           # MIRROR_0 ≠ MIRROR_100; *_tour16 не в счёт
        j = json.load(open(f)); h = j['hist']
        assert len(h) == gens + 1, f'{f}: длина hist {len(h)}, нужна {gens + 1}'
        assert [x['gen'] for x in h] == list(range(gens + 1)), f'{f}: поколения не подряд'
        C = np.array([x['claimed'] for x in h], float); T = np.array([x['true'] for x in h], float)
        assert np.isfinite(C).all() and np.isfinite(T).all(), f'{f}: NaN'
        runs[(task, int(tail))] = (C, T)
    if expect is not None:
        tasks = sorted({k[0] for k in runs})
        assert len(tasks) == expect[0] and all(sum(1 for k in runs if k[0] == t) == expect[1] for t in tasks), \
            f'{folder} {arm}: задач {len(tasks)}, прогонов {len(runs)}, ждали {expect[0]} × {expect[1]}'
    return runs

def win(v, lo, hi):
    """Среднее по поколениям lo..hi включительно."""
    assert 0 <= lo <= hi < len(v), (lo, hi, len(v))
    return float(np.mean(v[lo:hi + 1]))

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

# ───────── сверка ─────────
def per_seed(keys, vals, task=None):
    """Значения по сидам: для одной задачи — как есть, для всех задач — среднее по задачам внутри сида."""
    kv = [(k, v) for k, v in zip(keys, vals) if task is None or k[0] == task]
    return [k for k, _ in kv], [v for _, v in kv]

def dose_block(folder, early=EARLY, late=LATE, gens=GENS, expect=None):
    R = {}
    arms = {a: load(folder, a, gens, expect) for a, _ in DOSES}
    keys = sorted(set.intersection(*[set(v) for v in arms.values()]))
    if not keys: return {'нет данных': True}
    W = {a: np.array([win(arms[a][k][0] - arms[a][k][1], *late) for k in keys]) for a, _ in DOSES}
    Tl = {a: np.array([win(arms[a][k][1], *late) for k in keys]) for a, _ in DOSES}
    q = np.array([d for _, d in DOSES]); qc = q - q.mean()
    slope = [float(np.dot(qc, [W[a][i] for a, _ in DOSES]) / np.dot(qc, qc)) for i in range(len(keys))]
    neg_slope = [-x for x in slope]
    d1 = list(W['MIRROR_0'] - W['MIRROR_25']); d2 = list(W['MIRROR_50'] - W['MIRROR_100'])
    # предсказания с вердиктом: A — на T2 четверть свежих снижает завышение; B — на T3 наклон отрицателен; C — наклон по всем задачам
    R['A_T2_M25_below_M0'] = dict(directional(*per_seed(keys, d1, 'T2')), runs=counts(per_seed(keys, d1, 'T2')[1]))
    R['B_T3_slope_negative'] = dict(directional(*per_seed(keys, neg_slope, 'T3')), runs=counts(per_seed(keys, neg_slope, 'T3')[1]))
    R['C_all_tasks_slope_negative'] = dict(directional(keys, neg_slope), by_task=by_task(keys, neg_slope))
    # описательно: остальные пары и задачи
    R['desc_M25_below_M0_by_task'] = by_task(keys, d1); R['desc_M100_below_M50_by_task'] = by_task(keys, d2)
    tasks = sorted({k[0] for k in keys})
    idx = {t: [i for i, k in enumerate(keys) if k[0] == t] for t in tasks}
    R['desc_dose_means_by_task'] = {t: {a: round(float(W[a][idx[t]].mean()), 5) for a, _ in DOSES} for t in tasks}
    R['desc_truth_means_by_task'] = {t: {a: round(float(Tl[a][idx[t]].mean()), 5) for a, _ in DOSES} for t in tasks}
    R['desc_solved_share_by_task'] = {t: {a: round(float(np.mean(Tl[a][idx[t]] > 0.999)), 3) for a, _ in DOSES} for t in tasks}
    R['desc_degenerate_share_by_task'] = {t: {a: round(float(np.mean(Tl[a][idx[t]] < 0.001)), 3) for a, _ in DOSES} for t in tasks}
    R['desc_dose_means'] = {a: round(float(W[a].mean()), 5) for a, _ in DOSES}
    # ставка B1: нормированный наклон на T3, b = (наклон средних по дозе) / (среднее завышение без свежих).
    # Разбавление с полом даёт b от −1 до 0; отклик поведения без пола (М3′) — не выше −1.
    def norm_slope(ix):
        m0 = float(W['MIRROR_0'][ix].mean())
        return (float(np.dot(qc, [W[a][ix].mean() for a, _ in DOSES]) / np.dot(qc, qc)) / m0) if m0 > 0.02 else None
    for t in tasks:
        b = norm_slope(idx[t])
        if b is None: R[f'desc_norm_slope_{t}'] = dict(b=None, note='среднее завышение при MIRROR_0 не больше 0,02: отношение не определено'); continue
        by = {}
        for i in idx[t]: by.setdefault(keys[i][1], []).append(i)
        seeds = sorted(by); r = np.random.default_rng(0); bs = []
        for _ in range(4000):
            ix = np.concatenate([by[seeds[j]] for j in r.integers(0, len(seeds), len(seeds))]); v = norm_slope(ix)
            if v is not None: bs.append(v)
        R[f'desc_norm_slope_{t}'] = dict(b=round(b, 3), ci95=[round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)],
                                         ratios_to_M0={a: round(float(W[a][idx[t]].mean()) / float(W['MIRROR_0'][idx[t]].mean()), 3) for a, _ in DOSES})
    b3 = R.get('desc_norm_slope_T3', {}).get('b')
    R['B1_T3_norm_slope_between_minus1_and_0'] = dict(b=b3, holds=(bool(-1 < b3 < 0) if b3 is not None else None))
    w1 = R['desc_dose_means_by_task'].get('T1')
    R['B2_T1_M0_below_M25'] = dict(M0=w1['MIRROR_0'], M25=w1['MIRROR_25'], holds=bool(w1['MIRROR_0'] < w1['MIRROR_25'])) if w1 else None
    return R

def fixed_block(folder, arm, early=EARLY, late=LATE, gens=GENS, expect=None):
    """Описательно: рост завышения и доля правды в поздних приростах при постоянных тестах."""
    runs = load(folder, arm, gens, expect)
    if not runs: return {'нет данных': True}
    keys = sorted(runs)
    gap = {k: runs[k][0] - runs[k][1] for k in keys}
    d = [win(gap[k], *late) - win(gap[k], *early) for k in keys]
    dC = [win(runs[k][0], *late) - win(runs[k][0], *early) for k in keys]
    dT = [win(runs[k][1], *late) - win(runs[k][1], *early) for k in keys]
    Wl = [win(gap[k], *late) for k in keys]
    changed = [i for i in range(len(keys)) if abs(dC[i]) > TIE or abs(dT[i]) > TIE]
    R = dict(runs=len(keys), gap_growth=counts(d), gap_growth_by_task=by_task(keys, d), seed_level=directional(keys, d),
             late_gap=counts(Wl), runs_with_change=len(changed),
             growth_where_late_gap_positive=counts([d[i] for i in range(len(keys)) if Wl[i] > TIE]) if any(w > TIE for w in Wl) else None,
             truth_change=counts(dT), truth_change_by_task=by_task(keys, dT),
             min_step_of_claim=round(float(min(np.min(np.diff(runs[k][0])) for k in keys)), 6))
    sC, sT = float(np.sum(dC)), float(np.sum(dT))
    R['truth_share_of_late_gain'] = round(sT / sC, 3) if sC > 1e-9 else None      # сколько правды в приросте заявки между окнами
    dC0 = [win(runs[k][0], *early) - runs[k][0][0] for k in keys]; dT0 = [win(runs[k][1], *early) - runs[k][1][0] for k in keys]
    R['truth_share_of_early_gain'] = round(float(np.sum(dT0)) / float(np.sum(dC0)), 3) if float(np.sum(dC0)) > 1e-9 else None
    return R

def fresh_block(folder, arm, early=EARLY, late=LATE, gens=GENS, expect=None):
    runs = load(folder, arm, gens, expect)
    if not runs: return {'нет данных': True}
    keys = sorted(runs)
    d = [win(runs[k][0] - runs[k][1], *late) - win(runs[k][0] - runs[k][1], *early) for k in keys]
    Wl = [win(runs[k][0] - runs[k][1], *late) for k in keys]
    return dict(runs=len(keys), gap_growth=counts(d), late_gap=counts(Wl), late_gap_ci95=cluster_ci(keys, Wl))

def analyze(evo01, evo03, evo06, early=EARLY, late=LATE, gens=GENS, strict=True):
    e3 = (3, 20) if strict else None; e6 = (6, 20) if strict else None
    R = dict(alpha_side=ALPHA_SIDE, windows=dict(early=early, late=late))
    R['EVO03_dose'] = dose_block(evo03, early, late, gens, e3)
    R['EVO01_FIXED16'] = fixed_block(evo01, 'FIXED16', early, late, gens, e3)
    R['EVO06_FIXED32'] = fixed_block(evo06, 'FIXED32', early, late, gens, e6)
    for name, folder, arm, ex in (('EVO01_RANDOM16', evo01, 'RANDOM16', e3), ('EVO06_SAME16', evo06, 'SAME16', e6), ('EVO06_SAME32', evo06, 'SAME32', e6)):
        R[name] = fresh_block(folder, arm, early, late, gens, ex)
    # описательные ставки (без вердикта)
    def share_pos(c): n = c['pos'] + c['neg']; return (round(c['pos'] / n, 3) if n else None)
    for name, key in (('B3_FIXED16_gap_grows_in_majority', 'EVO01_FIXED16'), ('B4_FIXED32_gap_grows_in_majority', 'EVO06_FIXED32')):
        f = R.get(key, {})
        if 'gap_growth' in f:
            sh = share_pos(f['gap_growth']); R[name] = dict(share_positive_among_changed=sh, holds=(bool(sh > 0.5) if sh is not None else None))
    s16, s32 = load(evo06, 'SAME16', gens, e6), load(evo06, 'SAME32', gens, e6)
    kk = sorted(set(s16) & set(s32))
    if kk:
        g16 = np.array([win(s16[k][0] - s16[k][1], *late) for k in kk]); g32 = np.array([win(s32[k][0] - s32[k][1], *late) for k in kk])
        uns = np.array([win(s16[k][1], *late) < 0.999 and win(s32[k][1], *late) < 0.999 for k in kk])      # обе ветви не решили задачу
        m32 = float(g32.mean())
        R['B5_SAME32_mean_gap'] = dict(mean16=round(float(g16.mean()), 5), mean32=round(m32, 5), holds=bool(0.0083 <= m32 <= 0.0167),
                                       ratio=(round(float(g16.mean()) / m32, 3) if m32 > 1e-9 else None), pairs_both_unsolved=int(uns.sum()),
                                       ratio_both_unsolved=(round(float(g16[uns].mean()) / float(g32[uns].mean()), 3) if uns.any() and g32[uns].mean() > 1e-9 else None))
    f16 = R.get('EVO01_FIXED16', {})
    if 'truth_change' in f16:
        tc = f16['truth_change']; n = tc['pos'] + tc['neg']
        R['B6_FIXED16_truth_declines_in_majority'] = dict(declines=tc['neg'], rises=tc['pos'], ties=tc['ties'], share=(round(tc['neg'] / n, 3) if n else None),
                                                          holds=(bool(tc['neg'] > n / 2) if n else None))
    for name, key in (('B7a_FIXED32_late_gains_less_true_than_early', 'EVO06_FIXED32'), ('B7b_FIXED16_late_gains_less_true_than_early', 'EVO01_FIXED16')):
        f = R.get(key, {})
        if f.get('truth_share_of_late_gain') is not None and f.get('truth_share_of_early_gain') is not None:
            R[name] = dict(late=f['truth_share_of_late_gain'], early=f['truth_share_of_early_gain'], holds=bool(f['truth_share_of_late_gain'] < f['truth_share_of_early_gain']))
    return R

# ───────── самопроверка ─────────
def selftest():
    import tempfile
    d = tempfile.mkdtemp(); r = np.random.default_rng(5); g = np.arange(151)
    def write(folder, task, arm, seed, C, T):
        os.makedirs(folder, exist_ok=True)
        json.dump(dict(hist=[dict(gen=int(i), claimed=float(C[i]), true=float(T[i])) for i in range(151)]), open(os.path.join(folder, f'{task}_{arm}_s{seed}.json'), 'w'))
    ok = []
    # 1. окна: точные средние на «лестнице» — сдвиг на одно поколение и срез без правой границы дают другое число
    v = np.where(g < 11, 0.0, np.where(g <= 40, g * 1.0, np.where(g <= 120, 0.0, g * 2.0)))
    ok += [abs(win(v, *EARLY) - np.mean(np.arange(11, 41))) < 1e-12, abs(win(v, *LATE) - 2 * np.mean(np.arange(121, 151))) < 1e-12]
    try: win(v, 122, 151); ok.append(False)
    except AssertionError: ok.append(True)
    # 2. точный перебор знаков: 8 положительных значений → p = 1/256 в сторону «вверх»
    pu, pd = signflip_p(np.arange(1, 9)); ok += [abs(pu - 1 / 256) < 1e-12, abs(pd - 1.0) < 1e-12]
    pu, pd = signflip_p([1, -1, 2, -2]); ok.append(abs(pu - pd) < 1e-12)
    K8 = [('T1', i) for i in range(8)]                                           # порог: 1/256 проходит, 9/256 — нет
    ok += [directional(K8, [1.0] * 8)['verdict'] == 'подтверждено', directional(K8, [-1.0] * 8)['verdict'] == 'обратный эффект',
           directional(K8, [1.0] * 7 + [-1.0])['verdict'] == 'не решено', abs(directional(K8, [1.0] * 7 + [-1.0])['p_predicted'] - 9 / 256) < 1e-6]
    # 3. синтетика: доза снижает завышение несимметрично (0,30 → 0,28 → 0,20 → 0,05); FIXED: ступени и точные ничьи
    for s in range(20):
        for t in ('T1', 'T2', 'T3'):
            T = np.full(151, 0.3)
            gaps = dict(T1=(0.05, 0.20, 0.28, 0.30), T2=(0.30, 0.0, 0.0, 0.0), T3=(0.30, 0.28, 0.20, 0.05))[t]   # задачи ведут себя по-разному
            for (arm, _), gap in zip(DOSES, gaps):
                write(d + '/e3', t, arm, s, T + gap + r.normal(0, 0.03, 151), T)
            if s < 8: Cf, Tf = T + 0.1, T                                         # 24 прогона без изменений: точные ничьи
            elif s < 16: Cf, Tf = T + 0.1 + 0.2 * (g >= 60), T                    # 24 прогона: заявка растёт ступенью, правда стоит
            else: Cf, Tf = T + 0.1 + 0.1 * (g >= 60), T + 0.3 * (g >= 60)         # 12 прогонов: правда растёт сильнее заявки
            write(d + '/e1', t, 'FIXED16', s, Cf, Tf)
            write(d + '/e1', t, 'RANDOM16', s, T + r.normal(0.02, 0.02, 151), T)
        for t in ('T1', 'T2', 'T3', 'T4', 'T5', 'T6'):
            T = np.full(151, 0.3)
            write(d + '/e6', t, 'FIXED32', s, T + 0.05, T)
            write(d + '/e6', t, 'SAME16', s, T + 0.02, T); write(d + '/e6', t, 'SAME32', s, T + 0.012, T)
    R = analyze(d + '/e1', d + '/e3', d + '/e6')
    D, F = R['EVO03_dose'], R['EVO01_FIXED16']
    ok += [D['A_T2_M25_below_M0']['seeds'] == 20, abs(D['A_T2_M25_below_M0']['mean'] - 0.30) < 0.01,          # знак: у большей дозы меньше
           D['A_T2_M25_below_M0']['verdict'] == 'подтверждено',
           D['B_T3_slope_negative']['verdict'] == 'подтверждено', D['C_all_tasks_slope_negative']['seeds'] == 20,
           D['C_all_tasks_slope_negative']['by_task']['T1']['mean'] < 0 < D['C_all_tasks_slope_negative']['by_task']['T3']['mean'],
           D['desc_M100_below_M50_by_task']['T3']['mean'] > 0.1, D['desc_M100_below_M50_by_task']['T1']['mean'] < 0,
           abs(D['desc_norm_slope_T3']['ratios_to_M0']['MIRROR_100'] - 0.05 / 0.30) < 0.04, D['B1_T3_norm_slope_between_minus1_and_0']['holds'] is False,
           D['desc_solved_share_by_task']['T1']['MIRROR_0'] == 0.0, D['B2_T1_M0_below_M25']['holds'] is True,
           F['gap_growth'] == dict(pos=24, neg=12, ties=24, median=0.0, mean=round((24 * 0.2 - 12 * 0.2) / 60, 5)),   # счёт ничьих и знаков точный
           F['runs_with_change'] == 36, abs(F['truth_share_of_late_gain'] - (12 * 0.3) / (24 * 0.2 + 12 * 0.1)) < 1e-3,
           F['min_step_of_claim'] == 0.0, R['EVO06_FIXED32']['gap_growth']['ties'] == 120,
           R['B3_FIXED16_gap_grows_in_majority'] == dict(share_positive_among_changed=round(24 / 36, 3), holds=True),
           R['B4_FIXED32_gap_grows_in_majority']['holds'] is None,
           R['B5_SAME32_mean_gap']['holds'] is True, abs(R['B5_SAME32_mean_gap']['mean32'] - 0.012) < 1e-9, abs(R['B5_SAME32_mean_gap']['ratio'] - 0.02 / 0.012) < 1e-3,
           R['B6_FIXED16_truth_declines_in_majority'] == dict(declines=0, rises=12, ties=48, share=0.0, holds=False)]
    # 4. целостность: короткий hist и NaN должны останавливать
    json.dump(dict(hist=[dict(gen=i, claimed=0.1, true=0.1) for i in range(100)]), open(d + '/e1/T1_FIXED16_s99.json', 'w'))
    try: load(d + '/e1', 'FIXED16'); ok.append(False)
    except AssertionError: ok.append(True)
    os.remove(d + '/e1/T1_FIXED16_s99.json')
    print('самопроверка:', sum(ok), 'из', len(ok), 'пройдено'); assert all(ok), ok

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'selftest':
        selftest()
    elif mode == 'pilot':
        P = os.path.join(HERE, 'pilot')
        print('Пилот DEFER-01 (сиды 996–998, 150 поколений). Средний C − T по блокам поколений 1–10, 11–40, 41–80, 81–120, 121–150; затем T в тех же блоках:')
        for arm in ('MIRROR_0', 'MIRROR_25', 'MIRROR_50', 'MIRROR_100', 'FIXED16', 'RANDOM16'):
            runs = load(P, arm)
            for k in sorted(runs):
                C, T = runs[k]; B = ((1, 10), (11, 40), (41, 80), (81, 120), (121, 150))
                print(f'  {arm:10s} {k[0]} s{k[1]}: C−T {[round(win(C - T, a, b), 3) for a, b in B]}; T {[round(win(T, a, b), 3) for a, b in B]}')
        R = dict(EVO03_dose=dose_block(P), FIXED16=fixed_block(P, 'FIXED16'), RANDOM16=fresh_block(P, 'RANDOM16'))
        for a in ('MIRROR_0', 'MIRROR_25', 'MIRROR_50', 'MIRROR_100'):
            rr = load(P, a); print('  поздний C−T по сидам,', a, {t: [round(win(rr[(t, sd)][0] - rr[(t, sd)][1], *LATE), 3) for sd in (996, 997, 998)] for t in ('T1', 'T2', 'T3')})
        P6 = os.path.join(EXP, '2026-09-27_EVO-06', 'pilot')
        R['EVO06_pilot_FIXED32_60gens'] = fixed_block(P6, 'FIXED32', (11, 30), (31, 60), 60)
        json.dump(R, open(os.path.join(P, 'pilot_results.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(json.dumps(R, ensure_ascii=False, indent=1))
    elif mode == 'test':
        R = analyze(os.path.join(EXP, '2026-09-26_EVO-01', 'runs'), os.path.join(EXP, '2026-09-26_EVO-03', 'runs'), os.path.join(EXP, '2026-09-27_EVO-06', 'runs'))
        json.dump(R, open(os.path.join(HERE, 'defer01_results.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(json.dumps(R, ensure_ascii=False, indent=1))
    else:
        print(__doc__)
