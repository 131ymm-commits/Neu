# EVO-06: анализ по PREREG-EVO-06.md. Использование: python3 evo06_analyze.py [каталог runs] [файл результата]
#   основной прогон: python3 evo06_analyze.py runs evo06_results.json;  пилот: EVO06_GENS=60 python3 evo06_analyze.py pilot pilot/pilot_results.json
# Меры по окну последних 30 поколений (121–150 при 150): |C−T|, знаковая C−T, незнание 1−T, ИОИ′ = (1−T)+|C−T|;
# пары (задача, сид), знаковый тест — точный биномиальный (полный перебор, scipy.stats.binom), порог пересчитывается
# по фактическому n без ничьих; p двустороннее = 2·min(P(X≥w), P(X≤w)); величина эффекта — медиана парной разности
# с бутстреп-интервалом 95 % (Монте-Карло, 4000 повторов, сид 0; порядок вызовов бутстрепа фиксирован кодом).
# Вердикты сравнения: «подтверждено» (побед ≥ порога), «обратный эффект» (обратных ≥ порога), «разницы нет» (ИД95 медианы
# парной разности целиком внутри ±δ, где δ — полуширина ИД95 медианы парной разности A/A (AA32 против SAME32) той же меры
# в этом же прогоне), иначе «не решено»; «n мало» — порога при таком n не существует.
# Загрузка: все json должны иметь один хеш `code` и gens = EVO06_GENS (150 по умолчанию; у пилота 60) с gens+1 записями hist,
# иначе стоп с именем файла. Ранний срез для ставки Правого — поколения 11–40 (hist[11:41]); в пилоте (60 поколений) — 11–30,
# чтобы не перекрываться с окном 31–60.
import sys, os, json, glob
import numpy as np
from scipy.stats import binom
from evo06 import late, WINDOW

RUNS = sys.argv[1] if len(sys.argv) > 1 else 'runs'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'evo06_results.json'
ALPHA = 0.05
EXPECT_GENS = int(os.environ.get('EVO06_GENS', 150))
NBOOT = 4000
SMOOTH, PIECEWISE = ['T1', 'T6'], ['T2', 'T3', 'T4', 'T5']
BASE_HALF_EVO05 = 0.044                     # ½ медианы |C−T| BASE (T2–T5, окно 121–150) по POSTHOC EVO-05
PRIMARY = ('SPLIT8+8', 'SAME16')            # первичная пара совета (синтез §1): бюджет 16 labels на поколение
rng = np.random.default_rng(0)

R, TOUR_RUNS, broken = {}, {}, []
for f in sorted(glob.glob(f'{RUNS}/*.json')):
    try:
        d = json.load(open(f))
    except json.JSONDecodeError as e:
        broken.append(f'{f}: {e}'); continue
    if 'hist' not in d: continue                                   # результаты анализа в том же каталоге (пилот)
    if d.get('gens') != EXPECT_GENS or len(d['hist']) != d['gens'] + 1:
        sys.exit(f'СТОП: {f}: gens={d.get("gens")}, записей hist {len(d["hist"])}; ожидается gens={EXPECT_GENS} и {EXPECT_GENS + 1} записей')
    if d.get('tour', 5) != 5: TOUR_RUNS[(d['task'], d['arm'], d['seed'], d['tour'])] = d; continue
    L = late(d['hist'])                     # пересчёт из hist — сверка с записанными полями
    for k, v in L.items(): assert abs(d[k] - v) < 1e-12, (f, k)
    d['degenerate'] = d['final_true'] < 0.1
    T = [h['true'] for h in d['hist']]
    d['no_pressure'] = float(np.mean(T[-WINDOW:])) <= float(np.mean(T[:10]))   # «давления не было» (правило Скептика)
    # заявка, накопленная за жизнь элиты (пуллинг свежих заявок той же программы) — разведочная мера
    C = [h['claimed'] for h in d['hist']]; pool = []
    for g in range(len(C)):
        a = d['hist'][g]['elite_age']; pool.append(float(np.mean(C[g - a:g + 1])))
    d['abs_pool_late'] = float(np.mean([abs(pool[g] - T[g]) for g in range(max(0, len(C) - WINDOW), len(C))]))
    early = d['hist'][11:41] if len(d['hist']) >= 151 else d['hist'][11:31]      # поколения 11–40; в пилоте 11–30
    d['signed_ct_early'] = float(np.mean([h['claimed'] - h['true'] for h in early]))
    d['drift_ct'] = d['signed_ct_late'] - d['signed_ct_early']                   # ставка Правого
    R[(d['task'], d['arm'], d['seed'])] = d
if broken: sys.exit('СТОП: битые json:\n  ' + '\n  '.join(broken))
if not R: sys.exit(f'{RUNS}: прогонов нет')
CODES = {d['code'] for d in list(R.values()) + list(TOUR_RUNS.values())}
if len(CODES) != 1:
    sys.exit('СТОП: разные хеши кода в json: ' + '; '.join(f'{c}: {[k for k, d in R.items() if d["code"] == c][:3]}…' for c in sorted(CODES)))
CODE = CODES.pop()
TASKS = sorted({k[0] for k in R}); ARMS = sorted({k[1] for k in R}); SEEDS = sorted({k[2] for k in R})
EARLY = '11–40' if EXPECT_GENS >= 150 else '11–30'
print(f'{RUNS}: {len(R)} прогонов, задачи {TASKS}, ветви {ARMS}, сиды {SEEDS[0]}–{SEEDS[-1]} ({len(SEEDS)}); gens={EXPECT_GENS}, хеш кода {CODE};'
      f' окно последних {WINDOW}, ранний срез {EARLY}')
MEAS = ['abs_ct_late', 'signed_ct_late', 'ign_late', 'ioi2_late', 'true_late', 'claimed_late', 'abs_cf_t_late', 'abs_cf_tf_late',
        'abs_pool_late', 'abs_ct_all', 'ioi', 'ignorance', 'deception', 'final_true']


def pairs(a, b, tasks):
    return [(t, s) for t in tasks for s in SEEDS if (t, a, s) in R and (t, b, s) in R]


def thresh(n, alpha):
    """Наименьшее k: P(X ≥ k | n, ½) ≤ alpha/2 (двусторонний точный; alpha — уровень теста)."""
    ks = [k for k in range(n + 1) if binom.sf(k - 1, n, .5) <= alpha / 2]
    return ks[0] if ks else None                                       # None — n слишком мало для порога (пилот)


def p_two(wins, n):
    return float(min(1, 2 * min(binom.sf(wins - 1, n, .5), binom.cdf(wins, n, .5)))) if n else None


def boot_ci(x, stat=np.median):
    x = np.asarray(x)
    if not len(x): return [None, None]
    b = [float(stat(rng.choice(x, len(x)))) for _ in range(NBOOT)]
    return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]


def fp(p): return f'{p:.4f}' if p is not None else '—'


def cmp(a, b, m, tasks, alpha=ALPHA, lower_better=True, exclude=None, delta=None):
    """Победы a над b по мере m (строго меньше, если lower_better). exclude: функция (da, db) → True, если пару исключить.
    delta — полоса «разницы нет» для ИД95 медианы парной разности (None — исход «разницы нет» не выдаётся)."""
    P = pairs(a, b, tasks)
    if exclude: P = [(t, s) for t, s in P if not exclude(R[(t, a, s)], R[(t, b, s)])]
    da = np.array([R[(t, a, s)][m] for t, s in P]); db = np.array([R[(t, b, s)][m] for t, s in P])
    d = db - da if lower_better else da - db                       # > 0 — победа a
    wins, rev, ties = int((d > 0).sum()), int((d < 0).sum()), int((d == 0).sum())
    n = wins + rev; k = thresh(n, alpha); ci = boot_ci(d)
    if k is None: v = 'n мало'
    elif wins >= k: v = 'подтверждено'
    elif rev >= k: v = 'обратный эффект'
    elif delta is not None and ci[0] is not None and -delta <= ci[0] and ci[1] <= delta: v = 'разницы нет'
    else: v = 'не решено'
    return dict(a=a, b=b, measure=m, tasks=tasks, n_pairs=len(P), wins=wins, reverse=rev, ties=ties, n_eff=n, threshold=k, alpha=alpha,
                p_two_sided=p_two(wins, n), verdict=v, delta=delta, median_diff=float(np.median(d)) if len(d) else None, ci95=ci)


_AA = {}
def aa_delta(m, tasks):
    """δ — полуширина ИД95 медианы парной разности A/A (AA32 против SAME32) по мере m на тех же задачах; None без A/A."""
    key = (m, tuple(tasks))
    if key not in _AA:
        _AA[key] = cmp('AA32', 'SAME32', m, tasks) if has('AA32', 'SAME32') and pairs('AA32', 'SAME32', tasks) else None
    c = _AA[key]
    return (None if c is None or c['ci95'][0] is None else (c['ci95'][1] - c['ci95'][0]) / 2), c


def holm(tests):
    """Поправка Холма по двусторонним p; поле holm_significant."""
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


def line(h, tag=''):
    return (f'{tag}{h["a"]} vs {h["b"]} [{h["measure"]}{" " + h["subset"] if "subset" in h else ""}]: побед {h["wins"]}, обратных {h["reverse"]}, ничьих {h["ties"]},'
            f' порог {h["threshold"]}/{h["n_eff"]} (α={h["alpha"]}), p={fp(h["p_two_sided"])}, медиана разности {fp(h["median_diff"])}'
            f' ИД95 {[round(x, 4) for x in h["ci95"]] if h["ci95"][0] is not None else "—"}, δ={fp(h["delta"])} → {h["verdict"]}')


has = lambda *arms: all(a in ARMS for a in arms)
out = dict(runs_dir=RUNS, n_runs=len(R), tasks=TASKS, arms=ARMS, seeds=SEEDS, window=WINDOW, gens=EXPECT_GENS, code=CODE, early_window=EARLY)
# --- таблица медиан по (задача, ветвь) ---
out['table'] = {f'{t}/{a}': {**{m: med(t, a, m) for m in MEAS},
                             'degenerate': sum(R[(t, a, s)]['degenerate'] for s in SEEDS if (t, a, s) in R),
                             'no_pressure': sum(R[(t, a, s)]['no_pressure'] for s in SEEDS if (t, a, s) in R),
                             'n': sum((t, a, s) in R for s in SEEDS)}
                for t in TASKS for a in ARMS if any((t, a, s) in R for s in SEEDS)}
out['table_T2-T5'] = {a: {m: float(np.median([R[(t, a, s)][m] for t in PIECEWISE for s in SEEDS if (t, a, s) in R]))
                          for m in MEAS if any((t, a, s) in R for t in PIECEWISE for s in SEEDS)}
                      for a in ARMS if any((t, a, s) in R for t in PIECEWISE for s in SEEDS)}

# --- A/A (первым: даёт δ для полосы «разницы нет»; интервал нуля — по n_eff каждой меры отдельно) ---
if has('AA32', 'SAME32'):
    aa = {}
    for m in ('ioi2_late', 'ign_late', 'abs_ct_late'):
        _, c = aa_delta(m, TASKS); n = c['n_eff']
        c['null_interval_95'] = [int(binom.ppf(0.025, n, .5)), int(binom.ppf(0.975, n, .5))] if n else None
        c['inside'] = bool(c['null_interval_95'][0] <= c['wins'] <= c['null_interval_95'][1]) if n else None
        aa[m] = c
    out['AA'] = dict(tests=aa, inside=all(x['inside'] for x in aa.values() if x['inside'] is not None),
                     delta={m: (x['ci95'][1] - x['ci95'][0]) / 2 for m, x in aa.items()})
    print('A/A (AA32 против SAME32):', '; '.join(f'{m}: побед {x["wins"]}/{x["n_eff"]} (нич. {x["ties"]}), интервал нуля {x["null_interval_95"]},'
                                              f' δ={out["AA"]["delta"][m]:.4f}' for m, x in aa.items()),
          '→', 'в норме' if out['AA']['inside'] else 'ВНЕ ИНТЕРВАЛА — конвейер под вопросом')


# --- ворота: проверка манипуляции (обе половины условия совета) ---
def gate_for(split, same):
    def signed(arm, only_nondeg=False):
        return np.array([R[k]['signed_ct_late'] for k in R if k[1] == arm and not (only_nondeg and R[k]['degenerate'])])
    v, s = signed(split), signed(same)
    ci_v, ci_s = boot_ci(v, np.mean), boot_ci(s, np.mean)
    vn, sn = signed(split, True), signed(same, True)
    ci_vn, ci_sn = boot_ci(vn, np.mean) if len(vn) else [None, None], boot_ci(sn, np.mean) if len(sn) else [None, None]
    aa_mean = None
    if has('AA32', 'SAME32'):                                                # интервал A/A для СРЕДНЕЙ знаковой C−T (бутстреп разности SAME32−AA32)
        dd = np.array([R[(t, 'SAME32', s_)]['signed_ct_late'] - R[(t, 'AA32', s_)]['signed_ct_late'] for t in TASKS for s_ in SEEDS if (t, 'AA32', s_) in R and (t, 'SAME32', s_) in R])
        aa_mean = boot_ci(dd, np.mean)
    h1 = cmp(split, same, 'signed_ct_late', TASKS)                           # проверка теоремы: знаковая C−T у SPLIT меньше, чем у SAME
    h1 = {k: h1[k] for k in ('a', 'b', 'measure', 'n_pairs', 'wins', 'reverse', 'ties', 'n_eff', 'median_diff', 'ci95')}   # без порога и вердикта
    P = pairs(split, same, TASKS)
    h1['closer_to_zero'] = int(sum(abs(R[(t, split, s_)]['signed_ct_late']) < abs(R[(t, same, s_)]['signed_ct_late']) for t, s_ in P))
    half1, half2 = bool(ci_v[0] <= 0 <= ci_v[1]), bool(ci_s[0] > 0)
    outcome = ('пройдены' if half1 and half2 else
               ('НЕ ПРОЙДЕНЫ: ИД SPLIT не содержит 0 — утечка выборки заявки в отбор?' if not half1 else 'НЕ ПРОЙДЕНЫ: ИД SAME содержит 0 — проклятия победителя не видно, H2 неинформативна'))
    return dict(split=split, same=same, n_split=len(v), split_mean_signed_ct=float(v.mean()), split_ci95=ci_v, split_contains_zero=half1,
                same_mean_signed_ct=float(s.mean()), same_ci95=ci_s, same_above_zero=half2,
                nondegenerate=dict(n_split=len(vn), split_mean=float(vn.mean()) if len(vn) else None, split_ci95=ci_vn,
                                   n_same=len(sn), same_mean=float(sn.mean()) if len(sn) else None, same_ci95=ci_sn),
                aa_mean_diff_ci95=aa_mean, H1_theorem_check=h1, passed=half1 and half2, outcome=outcome)


def print_gate(g, tag):
    r4 = lambda ci: [round(x, 4) for x in ci] if ci[0] is not None else '—'
    print(f'ВОРОТА {tag} ({g["split"]} / {g["same"]}): средняя знаковая C−T у {g["split"]} = {g["split_mean_signed_ct"]:.4f} ИД95 {r4(g["split_ci95"])}'
          f' (содержит 0: {g["split_contains_zero"]}); у {g["same"]} = {g["same_mean_signed_ct"]:.4f} ИД95 {r4(g["same_ci95"])} (выше 0: {g["same_above_zero"]}) → {g["outcome"]}')
    nd = g['nondegenerate']
    print(f'   без вырожденных: {g["split"]} n={nd["n_split"]} средняя {fp(nd["split_mean"])} ИД95 {r4(nd["split_ci95"])}; {g["same"]} n={nd["n_same"]} средняя {fp(nd["same_mean"])}'
          f' ИД95 {r4(nd["same_ci95"])}; интервал A/A средней разности SAME32−AA32: {r4(g["aa_mean_diff_ci95"]) if g["aa_mean_diff_ci95"] else "—"}')
    h = g['H1_theorem_check']
    print(f'   H1 (теорема, без порога): знаковая C−T {h["a"]} < {h["b"]}: побед {h["wins"]}/{h["n_eff"]} (нич. {h["ties"]}), ближе к нулю в {h["closer_to_zero"]}/{h["n_pairs"]},'
          f' медиана разности {fp(h["median_diff"])} ИД95 {r4(h["ci95"])}')


if has(*PRIMARY):
    out['gate'] = gate_for(*PRIMARY); print_gate(out['gate'], 'первичной пары')
if has('SPLIT16+16', 'SAME32'):
    out['gate_SPLIT16+16'] = gate_for('SPLIT16+16', 'SAME32'); print_gate(out['gate_SPLIT16+16'], 'вторичной пары (отчитываются, не блокируют)')

# --- первичные (совет, синтез §1): SPLIT8+8 против SAME16, бюджет 16 labels; Бонферрони на две = Холм на двух (α/2 каждая) ---
if has(*PRIMARY):
    if out['gate']['passed']:
        d2, _ = aa_delta('ioi2_late', TASKS); d3, _ = aa_delta('ign_late', TASKS)
        H2 = cmp('SPLIT8+8', 'SAME16', 'ioi2_late', TASKS, alpha=ALPHA / 2, delta=d2)
        H3 = cmp('SAME16', 'SPLIT8+8', 'ign_late', TASKS, alpha=ALPHA / 2, delta=d3)   # побед SAME16 по незнанию = SPLIT хуже
        k = H3['threshold']
        H3['verdict'] = ('n мало' if k is None else 'SPLIT хуже по незнанию' if H3['wins'] >= k else 'SPLIT лучше по незнанию (не хуже)' if H3['reverse'] >= k
                         else 'SPLIT не хуже' if d3 is not None and H3['ci95'][1] <= d3 else 'не решено')
        out['primary'] = dict(H2_ioi2=H2, H3_ignorance=H3)
        print(line(H2, 'H2: ')); print(line(H3, 'H3: '))
    else:
        out['primary'] = 'не вскрыто: ворота не пройдены'
        print('H2/H3: ворота не пройдены — не вскрыто')

# --- критерий «вдвое» (journal/DECISIONS.md, 27.09): |C−T| элиты ≤ ½ BASE при незнании не хуже; T2–T5; попарно с SAME16 ---
crit = {}
for cand, m in [('SPLIT16+16', 'abs_ct_late'), ('SPLIT8+8', 'abs_ct_late'), ('SAME32', 'abs_ct_late'),
                ('SPLIT16+16', 'abs_pool_late'), ('SPLIT8+8', 'abs_pool_late'), ('SAME32', 'abs_pool_late'), ('SAME16', 'abs_pool_late')]:
    if not has(cand, 'SAME16'): continue
    P = pairs(cand, 'SAME16', PIECEWISE)
    if not P: continue
    descriptive = cand == 'SAME16'                                     # база сама по накопленной заявке: описательно, без вердикта
    v = [R[(t, cand, s)][m] for t, s in P]; base = [R[(t, 'SAME16', s)]['abs_ct_late'] for t, s in P]
    ci = boot_ci(v); target = min(BASE_HALF_EVO05, float(np.median(base)) / 2)
    ign = cmp('SAME16', cand, 'ign_late', PIECEWISE)
    ign_state = ('тождественно (T совпадает по построению)' if ign['n_eff'] == 0 else 'n мало' if ign['threshold'] is None
                 else 'хуже базы' if ign['wins'] >= ign['threshold'] else 'не хуже')
    ign_ok = ign_state.startswith(('тождественно', 'не хуже'))
    verdict = ('описательно' if descriptive else 'не выполнен (незнание хуже базы)' if ign_state == 'хуже базы' else 'не выполнен' if ci[0] > target
               else 'ВЫПОЛНЕН' if ci[1] <= target and ign_ok else 'не решено')
    crit[f'{cand}/{m}'] = dict(candidate=cand, measure=m, descriptive=descriptive, n=len(P), median=float(np.median(v)), median_ci95=ci, target=target,
                               base_median=float(np.median(base)), half_base_here=float(np.median(base)) / 2, half_base_evo05=BASE_HALF_EVO05,
                               pairs_le_half_base=int(sum(x <= y / 2 for x, y in zip(v, base))),
                               ignorance_base_wins=ign['wins'], ignorance_n_eff=ign['n_eff'], ignorance_threshold=ign['threshold'], ignorance_state=ign_state,
                               verdict=verdict, passed=verdict == 'ВЫПОЛНЕН')
    c = crit[f'{cand}/{m}']
    print(f'КРИТЕРИЙ ВДВОЕ {cand} [{m}] T2–T5: медиана {c["median"]:.4f} ИД95 {[round(x, 4) for x in ci]} против цели {target:.4f} (½ базы здесь {c["half_base_here"]:.4f} / EVO-05 {BASE_HALF_EVO05});'
          f' пар ≤ ½ базы в паре {c["pairs_le_half_base"]}/{c["n"]}; побед базы по незнанию {ign["wins"]}/{ign["n_eff"]} (порог {ign["threshold"]}, {ign_state}) → {verdict}')
out['criterion_half'] = crit

# --- вторичные с поправкой Холма (δ — по A/A той же меры на тех же задачах) ---
sec = []
def add(a, b, m, tasks, **kw):
    d, _ = aa_delta(m, tasks); sec.append(cmp(a, b, m, tasks, delta=d, **kw)); return sec[-1]
if has('SPLIT16+16', 'SAME32'):                                        # бюджет 32 labels (позиция Левого): ИОИ′, |C−T|, незнание, старый ИОИ, самообман
    for m in ('ioi2_late', 'abs_ct_late', 'ioi', 'deception'): add('SPLIT16+16', 'SAME32', m, TASKS)
    add('SAME32', 'SPLIT16+16', 'ign_late', TASKS)
if has(*PRIMARY):                                                      # первичная пара по остальным мерам
    for m in ('abs_ct_late', 'ioi', 'deception'): add('SPLIT8+8', 'SAME16', m, TASKS)
    for tl, nm in ((SMOOTH, 'гладкие'), (PIECEWISE, 'кусочные')):      # разбивка H2
        add('SPLIT8+8', 'SAME16', 'ioi2_late', tl)['subset'] = nm
if has('FIXED32', 'SAME32'):
    add('SAME32', 'FIXED32', 'abs_ct_late', TASKS); add('SAME32', 'FIXED32', 'ioi2_late', TASKS)   # Гудхарт: постоянные тесты хуже
for a in ('SAME16', 'SAME32'):                                         # ставка Правого: C−T у контроля растёт по поколениям (порог α/2, как записано)
    if a in ARMS:
        P = [(t, s) for t in TASKS for s in SEEDS if (t, a, s) in R]
        d = np.array([R[(t, a, s)]['drift_ct'] for t, s in P]); wins, rev = int((d > 0).sum()), int((d < 0).sum()); n = wins + rev; k = thresh(n, ALPHA / 2)
        sec.append(dict(a=a, b='—', measure=f'drift_ct (C−T поздн. минус {EARLY} > 0)', tasks=TASKS, n_pairs=len(P), wins=wins, reverse=rev,
                        ties=len(P) - n, n_eff=n, threshold=k, alpha=ALPHA / 2, p_two_sided=p_two(wins, n), delta=None,
                        verdict=('n мало' if k is None else 'подтверждено' if wins >= k else 'обратный эффект (опровергнуто)' if rev >= k else 'не решено'),
                        median_diff=float(np.median(d)) if len(d) else None, ci95=boot_ci(d)))
out['secondary_holm'] = holm(sec)
for h in out['secondary_holm']:
    print(line(h, 'вторичное: ') + f', Холм {"да" if h["holm_significant"] else "нет"}')

# --- пол и потолок ---
if has('RANDEVAL', 'ORACLE'):
    fl = {a: float(np.median([R[k]['ioi2_late'] for k in R if k[1] == a])) for a in ARMS}
    out['floor_ceiling'] = dict(ioi2_medians=fl, ordered=bool(fl['ORACLE'] <= min(fl.values()) and fl['RANDEVAL'] >= max(fl.values())))
    print('пол/потолок ИОИ′ (медианы по всем прогонам):', {a: round(v, 3) for a, v in fl.items()}, '→', 'упорядочены' if out['floor_ceiling']['ordered'] else 'НЕ упорядочены')

# --- чувствительность H2: исключения (только описательно) ---
if has(*PRIMARY):
    both = lambda da, db: da['degenerate'] and db['degenerate']
    anyd = lambda da, db: da['degenerate'] or db['degenerate'] or da['no_pressure'] or db['no_pressure']
    d2, _ = aa_delta('ioi2_late', TASKS)
    out['sensitivity'] = dict(exclude_both_degenerate=cmp('SPLIT8+8', 'SAME16', 'ioi2_late', TASKS, alpha=ALPHA / 2, exclude=both, delta=d2),
                              exclude_any_flag=cmp('SPLIT8+8', 'SAME16', 'ioi2_late', TASKS, alpha=ALPHA / 2, exclude=anyd, delta=d2),
                              excluded_per_arm={a: dict(degenerate=int(sum(R[k]['degenerate'] for k in R if k[1] == a)),
                                                       no_pressure=int(sum(R[k]['no_pressure'] for k in R if k[1] == a))) for a in ARMS})
    print('чувствительность H2 (описательно): без пар с обеими вырожденными —', out['sensitivity']['exclude_both_degenerate']['wins'], '/',
          out['sensitivity']['exclude_both_degenerate']['n_eff'], out['sensitivity']['exclude_both_degenerate']['verdict'], '; без пар с любой пометкой —',
          out['sensitivity']['exclude_any_flag']['wins'], '/', out['sensitivity']['exclude_any_flag']['n_eff'], out['sensitivity']['exclude_any_flag']['verdict'])
    print('чувствительность: помечено по ветвям', out['sensitivity']['excluded_per_arm'])

# --- §7.9 разложение |C−T| у SAME32 (описательно, с оговоркой: C_fresh по 16 входам, C по 32 — шум выборки разный; не в Холм) ---
if 'SAME32' in ARMS:
    ks = [k for k in R if k[1] == 'SAME32']
    d = np.array([R[k]['abs_ct_late'] - R[k]['abs_cf_t_late'] for k in ks])
    out['decomposition_SAME32'] = dict(n=len(d), median_diff=float(np.median(d)), ci95=boot_ci(d), runs_cf_lt_ct=int((d > 0).sum()), ties=int((d == 0).sum()),
                                       note='описательно: |C−T| − |C_fresh−T| по прогону; C_fresh по 16 входам, C по 32')
    x = out['decomposition_SAME32']
    print(f'разложение SAME32 (описательно): |C−T| − |C_fresh−T|: медиана {x["median_diff"]:.4f} ИД95 {[round(y, 4) for y in x["ci95"]]}, |C_fresh−T| < |C−T| в {x["runs_cf_lt_ct"]}/{x["n"]} прогонов')

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
