# EVO-06: анализ по PREREG-EVO-06.md. Использование: python3 evo06_analyze.py [каталог runs] [файл результата]
# Меры по окну последних 30 поколений (121–150 при 150): |C−T|, знаковая C−T, незнание 1−T, ИОИ′ = (1−T)+|C−T|;
# пары (задача, сид), знаковый тест — точный биномиальный (полный перебор, scipy.stats.binom), порог пересчитывается
# по фактическому n без ничьих; величина эффекта — медиана парной разности с бутстреп-интервалом 95 % (Монте-Карло, 4000).
import sys, json, glob
import numpy as np
from scipy.stats import binom
from evo06 import late, WINDOW

RUNS = sys.argv[1] if len(sys.argv) > 1 else 'runs'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'evo06_results.json'
ALPHA = 0.05
SMOOTH, PIECEWISE = ['T1', 'T6'], ['T2', 'T3', 'T4', 'T5']
BASE_HALF_EVO05 = 0.044                     # ½ медианы |C−T| BASE (T2–T5, окно 121–150) по POSTHOC EVO-05
rng = np.random.default_rng(0)

R, TOUR_RUNS = {}, {}
for f in sorted(glob.glob(f'{RUNS}/*.json')):
    d = json.load(open(f))
    if 'hist' not in d: continue                                   # результаты анализа в том же каталоге (пилот)
    if d.get('tour', 5) != 5: TOUR_RUNS[(d['task'], d['arm'], d['seed'], d['tour'])] = d; continue
    L = late(d['hist'])                     # пересчёт из hist — сверка с записанными полями
    for k, v in L.items(): assert abs(d[k] - v) < 1e-12, (f, k)
    d['degenerate'] = d['final_true'] < 0.1
    T = [h['true'] for h in d['hist']]
    d['no_pressure'] = float(np.mean(T[-WINDOW:])) <= float(np.mean(T[:10]))   # «давления не было» (правило Скептика)
    # заявка, накопленная за жизнь элиты (пуллинг свежих заявок той же программы) — вторичная мера
    C = [h['claimed'] for h in d['hist']]; pool = []
    for g in range(len(C)):
        a = d['hist'][g]['elite_age']; pool.append(float(np.mean(C[g - a:g + 1])))
    d['abs_pool_late'] = float(np.mean([abs(pool[g] - T[g]) for g in range(len(C) - WINDOW, len(C))]))
    d['signed_ct_early'] = float(np.mean([h['claimed'] - h['true'] for h in d['hist'][11:41]]))   # поколения 11–40
    d['drift_ct'] = d['signed_ct_late'] - d['signed_ct_early']                                  # ставка Правого
    R[(d['task'], d['arm'], d['seed'])] = d
TASKS = sorted({k[0] for k in R}); ARMS = sorted({k[1] for k in R}); SEEDS = sorted({k[2] for k in R})
print(f'{RUNS}: {len(R)} прогонов, задачи {TASKS}, ветви {ARMS}, сиды {SEEDS[0]}–{SEEDS[-1]} ({len(SEEDS)})')
MEAS = ['abs_ct_late', 'signed_ct_late', 'ign_late', 'ioi2_late', 'true_late', 'claimed_late', 'abs_cf_t_late', 'abs_cf_tf_late',
        'abs_pool_late', 'abs_ct_all', 'ioi', 'ignorance', 'deception', 'final_true']


def pairs(a, b, tasks):
    return [(t, s) for t in tasks for s in SEEDS if (t, a, s) in R and (t, b, s) in R]


def thresh(n, alpha):
    """Наименьшее k: P(X ≥ k | n, ½) ≤ alpha/2 (двусторонний точный)."""
    ks = [k for k in range(n + 1) if binom.sf(k - 1, n, .5) <= alpha / 2]
    return ks[0] if ks else None                                       # None — n слишком мало для порога (пилот)


def cmp(a, b, m, tasks, alpha=ALPHA, lower_better=True, exclude=None):
    """Победы a над b по мере m (строго меньше, если lower_better). exclude: функция (da, db) → True, если пару исключить."""
    P = pairs(a, b, tasks)
    if exclude: P = [(t, s) for t, s in P if not exclude(R[(t, a, s)], R[(t, b, s)])]
    da = np.array([R[(t, a, s)][m] for t, s in P]); db = np.array([R[(t, b, s)][m] for t, s in P])
    d = db - da if lower_better else da - db                       # > 0 — победа a
    wins, rev, ties = int((d > 0).sum()), int((d < 0).sum()), int((d == 0).sum())
    n = wins + rev; k = thresh(n, alpha)
    boot = [float(np.median(rng.choice(d, len(d)))) for _ in range(4000)] if len(d) else [0.0]
    return dict(a=a, b=b, measure=m, tasks=tasks, n_pairs=len(P), wins=wins, reverse=rev, ties=ties, n_eff=n, threshold=k,
                p_two_sided=float(min(1, 2 * binom.sf(wins - 1, n, .5))) if n else None,
                verdict=('подтверждено' if k is not None and wins >= k else ('обратный эффект' if k is not None and rev >= k else 'разницы нет')),
                median_diff=float(np.median(d)) if len(d) else None, ci95=[float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))])


def holm(tests):
    """Поправка Холма по p-значениям; возвращает список с полем holm_significant."""
    order = sorted(range(len(tests)), key=lambda i: tests[i]['p_two_sided'] if tests[i]['p_two_sided'] is not None else 1)
    m = len(tests); sig = True
    for rank, i in enumerate(order):
        p = tests[i]['p_two_sided']; lvl = ALPHA / (m - rank)
        sig = sig and p is not None and p <= lvl
        tests[i]['holm_level'] = lvl; tests[i]['holm_significant'] = bool(sig)
    return tests


def med(t, a, m):
    v = [R[(t, a, s)][m] for s in SEEDS if (t, a, s) in R]
    return float(np.median(v)) if v else None


out = dict(runs_dir=RUNS, n_runs=len(R), tasks=TASKS, arms=ARMS, seeds=SEEDS, window=WINDOW)
# --- таблица медиан по (задача, ветвь) ---
out['table'] = {f'{t}/{a}': {**{m: med(t, a, m) for m in MEAS},
                             'degenerate': sum(R[(t, a, s)]['degenerate'] for s in SEEDS if (t, a, s) in R),
                             'no_pressure': sum(R[(t, a, s)]['no_pressure'] for s in SEEDS if (t, a, s) in R),
                             'n': sum((t, a, s) in R for s in SEEDS)}
                for t in TASKS for a in ARMS if any((t, a, s) in R for s in SEEDS)}
out['table_T2-T5'] = {a: {m: float(np.median([R[(t, a, s)][m] for t in PIECEWISE for s in SEEDS if (t, a, s) in R]))
                          for m in MEAS if any((t, a, s) in R for t in PIECEWISE for s in SEEDS)}
                      for a in ARMS if any((t, a, s) in R for t in PIECEWISE for s in SEEDS)}

has = lambda *arms: all(a in ARMS for a in arms)
# --- ворота: проверка манипуляции (знаковая C−T у SPLIT около нуля, у SAME больше) ---
if has('SPLIT16+16', 'SAME32'):
    v = np.array([R[(t, 'SPLIT16+16', s)]['signed_ct_late'] for t in TASKS for s in SEEDS if (t, 'SPLIT16+16', s) in R])
    boot = [float(np.mean(rng.choice(v, len(v)))) for _ in range(4000)]
    ci = [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]
    aa = None
    if has('AA32'):                                                    # интервал A/A: разброс средней знаковой C−T между SAME32 и AA32
        dd = np.array([R[(t, 'SAME32', s)]['signed_ct_late'] - R[(t, 'AA32', s)]['signed_ct_late'] for t in TASKS for s in SEEDS if (t, 'AA32', s) in R and (t, 'SAME32', s) in R])
        aa = [float(np.percentile(dd, 2.5)), float(np.percentile(dd, 97.5))]
    h1 = cmp('SPLIT16+16', 'SAME32', 'signed_ct_late', TASKS)          # знаковая C−T у SPLIT меньше, чем у SAME32 (проверка теоремы)
    out['gate'] = dict(split_mean_signed_ct=float(v.mean()), split_ci95=ci, contains_zero=ci[0] <= 0 <= ci[1], aa_interval=aa,
                       same32_mean_signed_ct=float(np.mean([R[(t, 'SAME32', s)]['signed_ct_late'] for t in TASKS for s in SEEDS if (t, 'SAME32', s) in R])),
                       H1_theorem_check=h1, passed=bool(ci[0] <= 0 <= ci[1]))
    print('ВОРОТА (манипуляция): средняя знаковая C−T у SPLIT16+16 =', round(v.mean(), 4), 'ИД95', [round(x, 4) for x in ci],
          '→', 'пройдены' if out['gate']['passed'] else 'НЕ ПРОЙДЕНЫ (вскрывать H2/H3 нельзя)', '| H1 (теорема):', h1['wins'], '/', h1['n_eff'], h1['verdict'])

# --- первичные: H2 |C−T| и H3 незнание, SPLIT16+16 против SAME32, Холм на 2 (порог при n=60 → 40) ---
if has('SPLIT16+16', 'SAME32'):
    H2 = cmp('SPLIT16+16', 'SAME32', 'abs_ct_late', TASKS, alpha=ALPHA / 2)
    H3 = cmp('SAME32', 'SPLIT16+16', 'ign_late', TASKS, alpha=ALPHA / 2)   # побед SAME32 по незнанию; SPLIT «не хуже», если побед SAME32 < порога
    H3['verdict'] = ('SPLIT не хуже' if H3['wins'] < H3['threshold'] else 'SPLIT хуже по незнанию') if H3['threshold'] else 'n мало'
    out['primary'] = dict(H2_abs_ct=H2, H3_ignorance=H3)
    for k, h in out['primary'].items():
        print(f'{k}: {h["a"]} < {h["b"]} по {h["measure"]}: побед {h["wins"]}, обратных {h["reverse"]}, ничьих {h["ties"]}, порог {h["threshold"]}/{h["n_eff"]},'
              f' p={h["p_two_sided"]:.4f}, медиана разности {h["median_diff"]:.4f} ИД95 {[round(x, 4) for x in h["ci95"]]} → {h["verdict"]}')

# --- критерий «вдвое» (journal/DECISIONS.md, 27.09): |C−T| элиты ≤ ½ BASE при незнании не хуже; T2–T5 ---
crit = {}
for cand, m in [('SPLIT16+16', 'abs_ct_late'), ('SPLIT8+8', 'abs_ct_late'), ('SAME32', 'abs_ct_late'),
                ('SPLIT16+16', 'abs_pool_late'), ('SPLIT8+8', 'abs_pool_late'), ('SAME16', 'abs_pool_late'), ('SAME32', 'abs_pool_late')]:
    if not has(cand, 'SAME16'): continue
    P = pairs(cand, 'SAME16', PIECEWISE)
    if not P: continue
    v = [R[(t, cand, s)][m] for t, s in P]; base = [R[(t, 'SAME16', s)]['abs_ct_late'] for t, s in P]
    ign = cmp('SAME16', cand, 'ign_late', PIECEWISE)
    crit[f'{cand}/{m}'] = dict(candidate=cand, measure=m, n=len(P), median=float(np.median(v)), base_median=float(np.median(base)),
                               half_base_here=float(np.median(base)) / 2, half_base_evo05=BASE_HALF_EVO05,
                               pairs_le_half_base=int(sum(x <= y / 2 for x, y in zip(v, base))),
                               ignorance_base_wins=ign['wins'], ignorance_threshold=ign['threshold'],
                               passed=bool(np.median(v) <= min(BASE_HALF_EVO05, np.median(base) / 2) and ign['threshold'] is not None and ign['wins'] < ign['threshold']))
    c = crit[f'{cand}/{m}']
    print(f'КРИТЕРИЙ ВДВОЕ {cand} [{m}] T2–T5: медиана {c["median"]:.4f} против ½ базы здесь {c["half_base_here"]:.4f} / EVO-05 {BASE_HALF_EVO05};'
          f' пар ≤ ½ базы {c["pairs_le_half_base"]}/{c["n"]}; побед базы по незнанию {ign["wins"]}/{ign["n_eff"]} (порог {ign["threshold"]}) → {"ВЫПОЛНЕН" if c["passed"] else "не выполнен"}')
out['criterion_half'] = crit

# --- вторичные с поправкой Холма ---
sec = []
if has('SAME16', 'SPLIT8+8'):
    sec += [cmp('SPLIT8+8', 'SAME16', 'abs_ct_late', TASKS), cmp('SPLIT8+8', 'SAME16', 'ioi2_late', TASKS), cmp('SAME16', 'SPLIT8+8', 'ign_late', TASKS)]
if has('SPLIT16+16', 'SAME32'):
    sec += [cmp('SPLIT16+16', 'SAME32', 'ioi2_late', TASKS), cmp('SPLIT16+16', 'SAME32', 'ioi', TASKS), cmp('SPLIT16+16', 'SAME32', 'deception', TASKS)]
    for tl, nm in ((SMOOTH, 'гладкие'), (PIECEWISE, 'кусочные')):
        c = cmp('SPLIT16+16', 'SAME32', 'abs_ct_late', tl); c['subset'] = nm; sec.append(c)
if has('FIXED32', 'SAME32'):
    sec += [cmp('SAME32', 'FIXED32', 'abs_ct_late', TASKS), cmp('SAME32', 'FIXED32', 'ioi2_late', TASKS)]   # Гудхарт: постоянные тесты хуже
for a in ('SAME32', 'SAME16'):                                         # ставка Правого: C−T у контроля растёт по поколениям
    if a in ARMS:
        P = [(t, s) for t in TASKS for s in SEEDS if (t, a, s) in R]
        d = np.array([R[(t, a, s)]['drift_ct'] for t, s in P]); wins = int((d > 0).sum()); n = int((d != 0).sum()); k = thresh(n, ALPHA)
        sec.append(dict(a=a, b='—', measure='drift_ct (C−T 121–150 минус 11–40 > 0)', tasks=TASKS, n_pairs=len(P), wins=wins, reverse=int((d < 0).sum()),
                        ties=len(P) - n, n_eff=n, threshold=k, p_two_sided=float(min(1, 2 * binom.sf(wins - 1, n, .5))) if n else None,
                        verdict='подтверждено' if k and wins >= k else 'разницы нет', median_diff=float(np.median(d)) if len(d) else None, ci95=None))
out['secondary_holm'] = holm(sec)
for h in out['secondary_holm']:
    print(f'вторичное: {h["a"]} vs {h["b"]} [{h["measure"]}{" " + h["subset"] if "subset" in h else ""}]: {h["wins"]}/{h["n_eff"]} (обр. {h["reverse"]}, нич. {h["ties"]}),'
          f' порог {h["threshold"]}, p={h["p_two_sided"]}, Холм {"да" if h["holm_significant"] else "нет"} → {h["verdict"]}')

# --- A/A ---
if has('AA32', 'SAME32'):
    aa = {m: cmp('AA32', 'SAME32', m, TASKS) for m in ('abs_ct_late', 'ign_late', 'ioi2_late')}
    n = aa['abs_ct_late']['n_eff']; lo, hi = (int(binom.ppf(0.025, n, .5)), int(binom.ppf(0.975, n, .5))) if n else (None, None)
    out['AA'] = dict(tests=aa, null_interval_95=[lo, hi], inside=all(lo <= x['wins'] <= hi for x in aa.values()) if n else None)
    print('A/A (AA32 против SAME32): побед', {m: f'{x["wins"]}/{x["n_eff"]}' for m, x in aa.items()}, 'интервал нуля', [lo, hi],
          '→', 'в норме' if out['AA']['inside'] else 'ВНЕ ИНТЕРВАЛА — конвейер под вопросом')

# --- пол и потолок ---
if has('RANDEVAL', 'ORACLE'):
    fl = {a: float(np.median([R[k]['ioi2_late'] for k in R if k[1] == a])) for a in ARMS}
    out['floor_ceiling'] = dict(ioi2_medians=fl, ordered=bool(fl['ORACLE'] <= min(fl.values()) and fl['RANDEVAL'] >= max(fl.values())))
    print('пол/потолок ИОИ′ (медианы по всем прогонам):', {a: round(v, 3) for a, v in fl.items()}, '→', 'упорядочены' if out['floor_ceiling']['ordered'] else 'НЕ упорядочены')

# --- чувствительность: исключения (только описательно) ---
if has('SPLIT16+16', 'SAME32'):
    both = lambda da, db: da['degenerate'] and db['degenerate']
    anyd = lambda da, db: da['degenerate'] or db['degenerate'] or da['no_pressure'] or db['no_pressure']
    out['sensitivity'] = dict(exclude_both_degenerate=cmp('SPLIT16+16', 'SAME32', 'abs_ct_late', TASKS, exclude=both),
                              exclude_any_flag=cmp('SPLIT16+16', 'SAME32', 'abs_ct_late', TASKS, exclude=anyd),
                              excluded_per_arm={a: dict(degenerate=int(sum(R[k]['degenerate'] for k in R if k[1] == a)),
                                                       no_pressure=int(sum(R[k]['no_pressure'] for k in R if k[1] == a))) for a in ARMS})
    print('чувствительность: исключено по ветвям', out['sensitivity']['excluded_per_arm'])

# --- TOUR (описательно) ---
if TOUR_RUNS:
    out['tour'] = {f'{t}/{a}/s{s}/tour{tr}': dict(abs_ct_late=d['abs_ct_late'], signed_ct_late=d['signed_ct_late'], ign_late=d['ign_late'], final_true=d['final_true'])
                   for (t, a, s, tr), d in TOUR_RUNS.items()}
    for k, v in out['tour'].items(): print('TOUR', k, {kk: round(vv, 3) for kk, vv in v.items()})

json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=1)
print('\nмедианы по (задача, ветвь), окно последних', WINDOW, 'поколений:')
print(f'{"ячейка":22s} {"T":>6s} {"C":>6s} {"|C−T|":>6s} {"C−T":>7s} {"1−T":>6s} {"ИОИ′":>6s} {"|Cf−T|":>7s} {"|Cpool−T|":>9s} {"вырожд":>6s} {"безДавл":>7s}')
for k, x in out['table'].items():
    print(f'{k:22s} {x["true_late"]:6.3f} {x["claimed_late"]:6.3f} {x["abs_ct_late"]:6.3f} {x["signed_ct_late"]:7.3f} {x["ign_late"]:6.3f} {x["ioi2_late"]:6.3f}'
          f' {x["abs_cf_t_late"]:7.3f} {x["abs_pool_late"]:9.3f} {x["degenerate"]:3d}/{x["n"]:<2d} {x["no_pressure"]:3d}/{x["n"]:<2d}')
print('сводно T2–T5:', {a: {m: round(v[m], 3) for m in ('abs_ct_late', 'ign_late', 'ioi2_late', 'abs_pool_late')} for a, v in out['table_T2-T5'].items()})
print('результат →', OUT)
