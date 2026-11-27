"""DEFER-01: слепая сверка моделей «отсрочки отбора» с уже сохранёнными прогонами EVO-01, EVO-03, EVO-06.
Новых прогонов миров и вызовов голов нет: скрипт читает только поля hist[g].claimed и hist[g].true из json.
  python3 defer01.py pilot   — пилот EVO-06 (сиды 996, 997; 60 поколений; в тест не входят): динамика и проверка кода
  python3 defer01.py selftest — проверка логики на синтетических данных с известным ответом
  python3 defer01.py test    — основная сверка (только после регистрации PREREG-DEFER-01.md); пишет defer01_results.json
"""
import glob, json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(HERE, '..')
ALPHA = 0.01
EARLY, LATE = (11, 40), (121, 150)            # окна поколений (включительно), как в ставке Правого EVO-06 §7.5

def binom_tail(n, k, p=0.5):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(max(k, 0), n + 1))

def threshold(n, alpha=ALPHA):
    for k in range(n + 2):
        if binom_tail(n, k) <= alpha: return k
    return None

def load(folder, arm, suffix=''):
    """{(задача, сид): (C по поколениям, T по поколениям)} для ветви arm."""
    runs = {}
    for f in sorted(glob.glob(os.path.join(folder, f'T*_{arm}_s*{suffix}.json'))):
        name = os.path.basename(f)[:-5]
        task, rest = name.split('_', 1)
        if rest.rsplit('_s', 1)[0] != arm: continue          # MIRROR_0 не должен захватить MIRROR_100 и т. п.
        tail = rest.rsplit('_s', 1)[1]
        if not tail.isdigit(): continue                       # файлы вида ..._s996_tour16 — не в счёт
        j = json.load(open(f))
        h = j['hist']
        runs[(task, int(tail))] = (np.array([x['claimed'] for x in h], float), np.array([x['true'] for x in h], float))
    return runs

def win(v, lo, hi):                            # среднее по окну поколений lo..hi включительно
    return float(np.mean(v[lo:hi + 1]))

def sign_test(diffs, direction=+1):
    """Знаковая проверка: побед = число diff нужного знака; ничьи (ровно 0) исключаются; порог по фактическому n."""
    d = np.array(diffs, float)
    wins, losses, ties = int(np.sum(direction * d > 0)), int(np.sum(direction * d < 0)), int(np.sum(d == 0))
    n = wins + losses
    k = threshold(n) if n > 0 else None
    if k is None or n < 10: verdict = 'n мало'
    elif wins >= k: verdict = 'подтверждено'
    elif losses >= k: verdict = 'обратный эффект'
    else: verdict = 'не решено'
    return dict(wins=wins, losses=losses, ties=ties, n=n, k=k, false_level=(round(binom_tail(n, k), 4) if k is not None else None), verdict=verdict)

def boot_ci(x, stat=np.median, B=4000, seed=0):
    x = np.array(x, float); r = np.random.default_rng(seed)
    s = [stat(x[r.integers(0, len(x), len(x))]) for _ in range(B)]
    return [round(float(np.percentile(s, 2.5)), 4), round(float(np.percentile(s, 97.5)), 4)]

def growth(runs, early=EARLY, late=LATE):
    """d = (C − T) в позднем окне минус (C − T) в раннем, по прогонам; и то же для одной правды T."""
    keys = sorted(runs)
    d_gap = [win(runs[k][0] - runs[k][1], *late) - win(runs[k][0] - runs[k][1], *early) for k in keys]
    d_true = [win(runs[k][1], *late) - win(runs[k][1], *early) for k in keys]
    return keys, d_gap, d_true

def describe(x):
    return dict(median=round(float(np.median(x)), 4), ci95_median=boot_ci(x), mean=round(float(np.mean(x)), 4), ci95_mean=boot_ci(x, np.mean))

def analyze(evo01, evo03, evo06, early=EARLY, late=LATE):
    R = {}
    # P1, P2 — обман копится при постоянных тестах (М3): рост C − T от раннего окна к позднему
    for name, folder, arm in (('P1_EVO01_FIXED16', evo01, 'FIXED16'), ('P2_EVO06_FIXED32', evo06, 'FIXED32')):
        runs = load(folder, arm)
        if not runs: R[name] = 'нет данных'; continue
        _, dg, dt = growth(runs, early, late)
        R[name] = dict(runs=len(runs), test=sign_test(dg, +1), effect=describe(dg))
        if name.startswith('P1'):               # P6 — вилка: падает ли сама правда (вытеснение) — описательно
            R['P6_EVO01_FIXED16_truth_declines'] = dict(test=sign_test(dt, -1), effect=describe(dt))
    # сравнение с ветвями на свежих тестах (известный знак: спад) — описательно, для контраста
    for name, folder, arm in (('desc_EVO01_RANDOM16', evo01, 'RANDOM16'), ('desc_EVO06_SAME32', evo06, 'SAME32'), ('desc_EVO06_SAME16', evo06, 'SAME16')):
        runs = load(folder, arm)
        if runs:
            _, dg, dt = growth(runs, early, late)
            R[name] = dict(runs=len(runs), gap_growth=sign_test(dg, +1), effect=describe(dg), truth_change=describe(dt))
    # P3, P4 — доза свежих тестов (М3): поздний знаковый C − T ниже при большей доле свежих
    late_gap = {}
    for arm in ('MIRROR_0', 'MIRROR_25', 'MIRROR_50', 'MIRROR_100'):
        runs = load(evo03, arm)
        late_gap[arm] = {k: win(v[0] - v[1], *late) for k, v in runs.items()}
    for name, hi, lo in (('P3_EVO03_M25_below_M0', 'MIRROR_0', 'MIRROR_25'), ('P4_EVO03_M100_below_M50', 'MIRROR_50', 'MIRROR_100')):
        keys = sorted(set(late_gap[hi]) & set(late_gap[lo]))
        if not keys: R[name] = 'нет данных'; continue
        diffs = [late_gap[hi][k] - late_gap[lo][k] for k in keys]          # > 0: у большей дозы обман меньше
        R[name] = dict(pairs=len(keys), test=sign_test(diffs, +1), effect=describe(diffs))
    R['desc_EVO03_dose_medians'] = {arm: (round(float(np.median(list(v.values()))), 4) if v else None) for arm, v in late_gap.items()}
    R['desc_EVO03_dose_means'] = {arm: (round(float(np.mean(list(v.values()))), 4) if v else None) for arm, v in late_gap.items()}
    # P5 — масштаб проклятия победителя: отношение среднего знакового C − T у SAME16 и SAME32 (ожидание от sqrt(2) до 2)
    s16, s32 = load(evo06, 'SAME16'), load(evo06, 'SAME32')
    keys = sorted(set(s16) & set(s32))
    if keys:
        g16 = np.array([win(s16[k][0] - s16[k][1], *late) for k in keys]); g32 = np.array([win(s32[k][0] - s32[k][1], *late) for k in keys])
        r = np.random.default_rng(0); ratios = []
        for _ in range(4000):
            i = r.integers(0, len(keys), len(keys))
            if g32[i].mean() != 0: ratios.append(g16[i].mean() / g32[i].mean())
        R['P5_EVO06_winner_curse_ratio'] = dict(pairs=len(keys), mean16=round(float(g16.mean()), 4), mean32=round(float(g32.mean()), 4),
                                                 ratio=(round(float(g16.mean() / g32.mean()), 3) if g32.mean() != 0 else None),
                                                 ci95=[round(float(np.percentile(ratios, 2.5)), 3), round(float(np.percentile(ratios, 97.5)), 3)])
    return R

def selftest():
    """Синтетика с известным ответом: рост 0,002 за поколение у «постоянных» и 0 у «свежих»; доза снижает разрыв."""
    import tempfile
    r = np.random.default_rng(5)
    d = tempfile.mkdtemp()
    def write(folder, task, arm, seed, C, T):
        os.makedirs(folder, exist_ok=True)
        json.dump(dict(hist=[dict(gen=g, claimed=float(C[g]), true=float(T[g])) for g in range(151)]), open(os.path.join(folder, f'{task}_{arm}_s{seed}.json'), 'w'))
    g = np.arange(151)
    for s in range(20):
        for t in ('T1', 'T2', 'T3'):
            T = 0.3 + r.normal(0, 0.01, 151)
            write(d + '/e1', t, 'FIXED16', s, T + 0.002 * g + r.normal(0, 0.02, 151), T)
            write(d + '/e1', t, 'RANDOM16', s, T + r.normal(0, 0.02, 151), T)
            write(d + '/e6', t, 'FIXED32', s, T + r.normal(0, 0.02, 151), T)            # роста нет → «не решено»
            write(d + '/e6', t, 'SAME16', s, T + 0.02 + r.normal(0, 0.01, 151), T)
            write(d + '/e6', t, 'SAME32', s, T + 0.012 + r.normal(0, 0.01, 151), T)
            for arm, gap in (('MIRROR_0', 0.3), ('MIRROR_25', 0.2), ('MIRROR_50', 0.1), ('MIRROR_100', 0.1)):
                write(d + '/e3', t, arm, s, T + gap + r.normal(0, 0.02, 151), T)
    R = analyze(d + '/e1', d + '/e3', d + '/e6')
    ok = [R['P1_EVO01_FIXED16']['test']['verdict'] == 'подтверждено',
          R['P2_EVO06_FIXED32']['test']['verdict'] == 'не решено',
          R['P3_EVO03_M25_below_M0']['test']['verdict'] == 'подтверждено',
          R['P4_EVO03_M100_below_M50']['test']['verdict'] == 'не решено',
          abs(R['P5_EVO06_winner_curse_ratio']['ratio'] - 0.02 / 0.012) < 0.15,
          abs(R['P1_EVO01_FIXED16']['effect']['median'] - 0.002 * 110) < 0.01,      # центры окон 25,5 и 135,5 → 110 поколений
          R['P3_EVO03_M25_below_M0']['pairs'] == 60, R['P1_EVO01_FIXED16']['runs'] == 60,
          threshold(60) == 40, threshold(120) == 74]
    print('самопроверка:', sum(ok), 'из', len(ok), 'пройдено'); assert all(ok), ok

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'selftest':
        selftest()
    elif mode == 'pilot':
        folder = os.path.join(EXP, '2026-09-27_EVO-06', 'pilot')
        print('Пилот EVO-06 (сиды 996, 997; 60 поколений). Средний C − T по блокам поколений:')
        for arm in ('FIXED32', 'SAME32', 'SAME16'):
            runs = load(folder, arm)
            for k in sorted(runs):
                C, T = runs[k]
                blocks = [round(float(np.mean((C - T)[a:b + 1])), 3) for a, b in ((1, 10), (11, 20), (21, 30), (31, 40), (41, 50), (51, 60))]
                tb = [round(float(np.mean(T[a:b + 1])), 3) for a, b in ((1, 10), (11, 30), (31, 60))]
                print(f'  {arm:8s} {k[0]} s{k[1]}: C−T {blocks}; T {tb}')
        for arm in ('FIXED32', 'SAME32', 'SAME16'):
            _, dg, dt = growth(load(folder, arm), (11, 30), (31, 60))
            print(f'  {arm}: рост C − T (31–60 минус 11–30) по прогонам: {[round(x, 3) for x in dg]}; изменение T: {[round(x, 3) for x in dt]}')
    elif mode == 'test':
        R = analyze(os.path.join(EXP, '2026-09-26_EVO-01', 'runs'), os.path.join(EXP, '2026-09-26_EVO-03', 'runs'), os.path.join(EXP, '2026-09-27_EVO-06', 'runs'))
        json.dump(R, open(os.path.join(HERE, 'defer01_results.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(json.dumps(R, ensure_ascii=False, indent=1))
    else:
        print(__doc__)
