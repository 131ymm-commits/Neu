"""CHILD-01 (О1 «Детство»): анализ прогонов.
  python3 child01_analyze.py selftest — проверка логики на синтетике с точным ответом
  python3 child01_analyze.py pilot    — пилотные сиды 990–992 (каталог pilot/)
  python3 child01_analyze.py test     — основной разбор (каталог runs/, только после регистрации); пишет child01_results.json
Единица проверки — сид; точная перестановка знаков полным перебором; 0,005 на сторону (stats01.py)."""
import glob, json, os, sys
import numpy as np
import stats01 as S
from child01 import parse_arm, is_exam, GENS

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS6 = ('T1', 'T2', 'T3', 'T4', 'T5', 'T6')
TASKS_INFL = ('T2', 'T3', 'T4', 'T5', 'T6')            # задачи, где у FIX в пилоте есть завышение показателя (у T1 — 0,001)
DOSES = (('FIX', 0.0), ('ALT_12', 0.125), ('ALT_25', 0.25), ('ALT_50', 0.5), ('ALT_75', 0.75), ('RND', 1.0))
ARMS = ('FIX', 'RND', 'ALT_12', 'ALT_25', 'ALT_50', 'ALT_75', 'NOISE_25', 'NOISE_50', 'MIX_25', 'MIX_50', 'FINAL_25', 'FINAL_50',
        'RND4', 'ALT_6_N64', 'ALT_25_T20')
LATE = (121, 150)                                      # поздние поколения включительно
EQ = 0.05                                              # граница «разницы нет» для проверки P4
EQ_SENS = 0.02                                         # та же проверка с узкой границей — чувствительность, вердикта не меняет
EQ_B = 0.1                                             # P2: «экзамен слеп к завышению», если |β_I| меньше этой доли β_T (оба — на стандартное отклонение признака)
INNER = ('ALT_12', 'ALT_25', 'ALT_50', 'ALT_75')       # внутренние дозы: наклон без концов FIX и RND
SERIES = ('c_key', 't_key', 'c_fix', 't_fix', 'cm_key', 'c_eb', 'to_key', 'mT', 'mI', 'uniq')


def load(folder, expect_seeds=None):
    R = {}
    for f in sorted(glob.glob(os.path.join(folder, '*.json'))):
        j = json.load(open(f)); k = (j['task'], j['arm'], j['seed'])
        name = os.path.basename(f)[:-5]
        assert name == f"{j['task']}_{j['arm']}_s{j['seed']}", f'{f}: имя и поля не совпадают'
        assert all(len(j['series'][s]) == GENS + 1 for s in SERIES), f'{f}: длина рядов'
        assert len(j['kinds']) == GENS + 1 and j['spec'] == parse_arm(j['arm']), f'{f}: расписание'
        sp = j['spec']
        for g in range(GENS):                                              # вид каждого поколения должен совпасть с правилом ветви
            want = 'M' if sp['kind'] == 'MIX' else (('N' if sp['kind'] == 'NOISE' else 'E') if is_exam(g, sp) else 'P')
            assert j['kinds'][g] == want, f'{f}: поколение {g}: {j["kinds"][g]} вместо {want}'
        assert all(np.isfinite(j['series'][s]).all() for s in SERIES), f'{f}: не число'
        assert all(len(j['grad'][k]) == GENS + 1 for k in ('bE_T', 'bE_I', 'sd_T', 'sd_I')), f'{f}: градиенты'
        R[k] = j
    if expect_seeds is not None:
        want = {(t, a, s) for t in TASKS6 for a in ARMS for s in expect_seeds}
        assert set(R) == want, f'{folder}: прогонов {len(R)}, ждали {len(want)}; нет: {sorted(want - set(R))[:5]}; лишние: {sorted(set(R) - want)[:5]}'
        assert len({j['code'] for j in R.values()}) == 1, 'прогоны сделаны разными версиями кода'
    return R


def win(v, lo, hi):
    assert 0 <= lo <= hi < len(v)
    return float(np.mean(v[lo:hi + 1]))


def metric(j, name):
    s = j['series']; a = lambda k: np.asarray(s[k], float)
    if name == 'W_ind': return win(a('c_fix') - a('t_fix'), *LATE)        # позднее завышение показателя у лучшего по показателю
    if name == 'T_ind': return win(a('t_fix'), *LATE)                      # поздняя правда лучшего по показателю
    if name == 'T_key': return win(a('t_key'), *LATE)                      # поздняя правда рабочей элиты
    if name == 'W_op': return win(a('c_key') - a('t_key'), *LATE)          # позднее завышение рабочей заявки
    if name == 'W_eb': return win(a('c_eb') - a('t_key'), *LATE)           # то же для заявки с усадкой
    if name == 'T_out': return win(a('to_key'), *LATE)                     # правда элиты вне обучающего диапазона
    if name == 'mT': return win(a('mT'), *LATE)
    if name == 'SE_I': return float(np.mean(j['win']['SE_I'][1:]))         # отбор по экзамену → завышение, поколения 31–150
    if name == 'SP_I': return float(np.mean(j['win']['SP_I'][1:]))
    if name == 'C_TI': return float(np.mean(j['win']['C_TI'][1:]))
    if name in ('bI', 'bT'):                                               # частный градиент отбора по экзамену на стандартное отклонение признака, слой T > 0
        g = j['grad']; b = g['bE_I'] if name == 'bI' else g['bE_T']; sd = g['sd_I'] if name == 'bI' else g['sd_T']
        only_exam = j['spec']['kind'] != 'FIX'                             # в FIX — все поколения 31–150; в остальных — только экзаменационные
        v = [b[x] * sd[x] for x in range(31, GENS + 1) if b[x] is not None and (not only_exam or j['kinds'][x] == 'E')]
        return float(np.mean(v)) if v else float('nan')
    if name == 'uniq': return win(a('uniq'), *LATE)
    if name == 'ign': return float(j['ignorance'])
    if name == 'dec': return float(j['deception'])
    raise KeyError(name)


def diff(R, name, arm_a, arm_b, tasks):
    """Пары (задача, сид): метрика(arm_a) − метрика(arm_b)."""
    keys = sorted({(t, s) for (t, a, s) in R if a == arm_a and t in tasks} & {(t, s) for (t, a, s) in R if a == arm_b and t in tasks})
    return keys, [metric(R[(t, arm_a, s)], name) - metric(R[(t, arm_b, s)], name) for t, s in keys]


def neg_slope(R, name, tasks, doses=DOSES):
    """Пары (задача, сид): минус наклон метрики по доле экзамена q через заданные дозы."""
    q = np.array([d for _, d in doses]); qc = q - q.mean()
    keys = sorted(set.intersection(*[{(t, s) for (t, a, s) in R if a == arm and t in tasks} for arm, _ in doses]))
    return keys, [-float(np.dot(qc, [metric(R[(t, arm, s)], name) for arm, _ in doses]) / np.dot(qc, qc)) for t, s in keys]


def test_dir(keys, vals, verdict=True):
    """Проверка направления по сидам. Вердикт «подтверждено» остаётся, только если знак среднего тот же не меньше чем в 4 задачах из 5
    (или в 5 из 6); иначе — «в среднем, неоднородно по задачам». verdict=False — описательный блок без вердикта."""
    keys = [k for k, v in zip(keys, vals) if v == v]; vals = [v for v in vals if v == v]              # без нечисел
    d = S.directional(keys, vals); d['by_task'] = S.by_task(keys, vals)
    nt = len(d['by_task']); same = sum(1 for x in d['by_task'].values() if x['mean'] > 0); d['tasks_positive'] = same; d['tasks_total'] = nt
    if d.get('verdict') == 'подтверждено' and same < nt - 1: d['verdict'] = 'в среднем, неоднородно по задачам'
    if not verdict: d.pop('verdict', None)
    return d


def cell_means(R, name):
    out = {}
    for a in ARMS:
        row = {}
        for t in TASKS6:
            v = [metric(R[k], name) for k in R if k[0] == t and k[1] == a]
            if v: row[t] = round(float(np.mean(v)), 4)
        if row: out[a] = dict(row, mean=round(float(np.mean(list(row.values()))), 4))
    return out


def arm_mean(R, name, arm, tasks):
    """Среднее по сидам от среднего по задачам."""
    seeds = sorted({s for (t, a, s) in R if a == arm})
    return float(np.mean([np.mean([metric(R[(t, arm, s)], name) for t in tasks if (t, arm, s) in R]) for s in seeds]))


def analyze(R):
    out = dict(alpha_side=S.ALPHA_SIDE, late=LATE, eq_margin=EQ, runs=len(R), seeds=sorted({k[2] for k in R}))
    # ── проверки с вердиктом ──
    out['P1a_dose_slope'] = test_dir(*neg_slope(R, 'W_ind', TASKS_INFL))
    out['P1b_inner_slope'] = test_dir(*neg_slope(R, 'W_ind', TASKS_INFL, [(a, q) for a, q in DOSES if a in INNER]))
    kf = sorted((t, s) for (t, a, s) in R if a == 'FIX' and t in TASKS_INFL)
    bi = [metric(R[(t, 'FIX', s)], 'bI') for t, s in kf]; bt = [metric(R[(t, 'FIX', s)], 'bT') for t, s in kf]
    d2 = test_dir(kf, bi); d2['beta_T_mean'] = round(float(np.nanmean(bt)), 5)
    if d2.get('verdict') != 'n мало':
        lo, hi = d2['ci95']; lim = EQ_B * abs(d2['beta_T_mean'])
        d2['blind_margin'] = round(lim, 5)
        d2['verdict'] = ('экзамен предпочитает завышенных' if d2['p_predicted'] <= S.ALPHA_SIDE else 'экзамен чистит' if d2['p_opposite'] <= S.ALPHA_SIDE
                         else 'экзамен слеп' if (-lim < lo and hi < lim) else 'не решено')
    out['P2_exam_gradient_on_inflation'] = d2
    ka = sorted((t, s) for (t, a, s) in R if a == 'ALT_50' and t in TASKS_INFL)                       # то же в экзаменационных поколениях ALT_50 — описательно
    out['D_P2_in_ALT50_exam_gens'] = dict(test_dir(ka, [metric(R[(t, 'ALT_50', s)], 'bI') for t, s in ka], verdict=False),
                                          beta_T_mean=round(float(np.nanmean([metric(R[(t, 'ALT_50', s)], 'bT') for t, s in ka])), 5))
    out['D_SE_I_full_shift_FIX'] = test_dir(kf, [metric(R[(t, 'FIX', s)], 'SE_I') for t, s in kf], verdict=False)      # полный сдвиг по Прайсу, включая груз мутаций
    out['P3_truth_ALT50_vs_NOISE50'] = test_dir(*diff(R, 'T_ind', 'ALT_50', 'NOISE_50', TASKS6))
    k4, v4 = diff(R, 'W_ind', 'NOISE_50', 'ALT_50', TASKS_INFL); d4 = test_dir(k4, v4)
    if d4.get('verdict') != 'n мало':
        lo, hi = d4['ci95']
        d4['verdict'] = ('экзамен чистит' if d4['p_predicted'] <= S.ALPHA_SIDE else 'обратный эффект' if d4['p_opposite'] <= S.ALPHA_SIDE
                         else 'разницы нет' if (-EQ < lo and hi < EQ) else 'не решено')
        d4['within_sens_margin'] = bool(-EQ_SENS < lo and hi < EQ_SENS)
    out['P4_purge_NOISE50_minus_ALT50'] = d4
    out['P5_popmean_truth_ALT25_vs_FINAL25'] = test_dir(*diff(R, 'mT', 'ALT_25', 'FINAL_25', TASKS6))
    out['D_P5_by_T_ind'] = test_dir(*diff(R, 'T_ind', 'ALT_25', 'FINAL_25', TASKS6), verdict=False)
    out['D_P5_by_T_key'] = test_dir(*diff(R, 'T_key', 'ALT_25', 'FINAL_25', TASKS6), verdict=False)
    out['D_truth_ALT25_vs_MIX25'] = test_dir(*diff(R, 'T_key', 'ALT_25', 'MIX_25', TASKS6), verdict=False)
    out['D_purge_NOISE25_minus_ALT25'] = test_dir(*diff(R, 'W_ind', 'NOISE_25', 'ALT_25', TASKS_INFL), verdict=False)
    out['D_truth_ALT25_vs_NOISE25'] = test_dir(*diff(R, 'T_ind', 'ALT_25', 'NOISE_25', TASKS6), verdict=False)
    out['D_noise_slope'] = test_dir(*neg_slope(R, 'W_ind', TASKS_INFL, [('FIX', 0.0), ('NOISE_25', 0.25), ('NOISE_50', 0.5)]), verdict=False)
    out['D_uniq_FINAL25_minus_ALT25'] = test_dir(*diff(R, 'uniq', 'FINAL_25', 'ALT_25', TASKS6), verdict=False)
    # ── описательные ставки (без вердикта) ──
    m = lambda name, arm, tasks=TASKS6: arm_mean(R, name, arm, tasks)
    B = {}
    w0, w5, w1 = m('W_ind', 'FIX', TASKS_INFL), m('W_ind', 'ALT_50', TASKS_INFL), m('W_ind', 'RND', TASKS_INFL)
    e = (w5 - w1) / (w0 - w1) if abs(w0 - w1) > 1e-9 else None
    B['B1_excess_at_half_in_0.3_0.7'] = dict(value=None if e is None else round(e, 3), holds=None if e is None else bool(0.3 <= e <= 0.7))
    c = m('T_key', 'ALT_25') - 0.75 * m('T_key', 'FIX') - 0.25 * m('T_key', 'RND')
    B['B2_truth_concave'] = dict(value=round(c, 4), holds=bool(c > 0))
    d = m('T_key', 'ALT_12') - m('T_key', 'RND')
    B['B3_eighth_not_worse_than_always'] = dict(value=round(d, 4), holds=bool(d >= -0.03))
    d = m('T_key', 'FINAL_25') - m('T_key', 'FIX')
    B['B4_final_exam_adds_little_truth'] = dict(value=round(d, 4), holds=bool(abs(d) < 0.03))
    d = m('T_key', 'FIX', ('T1',)) - m('T_key', 'RND', ('T1',))
    B['B5_T1_fixed_better_than_fresh'] = dict(value=round(d, 4), holds=bool(d > 0))
    eb = m('W_eb', 'RND'); B['B6a_shrunk_claim_unbiased_under_fresh'] = dict(value=round(eb, 4), holds=bool(abs(eb) <= 0.02))
    r = m('W_eb', 'FIX', TASKS_INFL) / m('W_op', 'FIX', TASKS_INFL) if m('W_op', 'FIX', TASKS_INFL) > 1e-9 else None
    B['B6b_shrunk_claim_keeps_inflation_under_fixed'] = dict(value=None if r is None else round(r, 3), holds=None if r is None else bool(r >= 0.7))
    d = m('T_key', 'ALT_25_T20') - m('T_key', 'ALT_25')
    B['B7_sharper_exam_not_better'] = dict(value=round(d, 4), holds=bool(d < 0))
    tb = {a: m('T_key', a) for a in ('RND4', 'ALT_25', 'ALT_6_N64')}
    B['B8_equal_budget_ALT25_best'] = dict(value={a: round(v, 4) for a, v in tb.items()}, holds=bool(max(tb, key=tb.get) == 'ALT_25'))
    d = m('W_ind', 'ALT_50', TASKS_INFL) - m('W_ind', 'MIX_50', TASKS_INFL)
    B['B9_mix_equals_alt_for_inflation'] = dict(value=round(d, 4), holds=bool(abs(d) < 0.03))
    out['bets'] = B
    # ── описательные таблицы ──
    out['tables'] = {n: cell_means(R, n) for n in ('W_ind', 'T_key', 'T_ind', 'W_op', 'W_eb', 'T_out', 'mT', 'ign', 'dec', 'SE_I', 'SP_I', 'C_TI', 'uniq')}
    out['solved_share'] = {a: {t: round(float(np.mean([metric(R[k], 'T_key') > 0.999 for k in R if k[0] == t and k[1] == a])), 3) for t in TASKS6} for a in ARMS
                           if any(k[1] == a for k in R)}
    out['labels_per_run'] = {a: int(np.mean([R[k]['labels_total'] for k in R if k[1] == a])) for a in ARMS if any(k[1] == a for k in R)}
    out['dose_curve_W_ind'] = {arm: round(m('W_ind', arm, TASKS_INFL), 4) for arm, _ in DOSES}
    out['dose_curve_T_key'] = {arm: round(m('T_key', arm), 4) for arm, _ in DOSES}
    return out


# ───────── самопроверка на синтетике с точным ответом ─────────
def synth(seeds=range(20), spec=None):
    """Синтетические прогоны: ряды постоянны в позднем окне (оно задано здесь числами), вне окна — мусор, чтобы ловить сдвиг окна."""
    spec = spec or {}
    R = {}
    for t in TASKS6:
        for a in ARMS:
            sp = parse_arm(a); q = sp['q'] if sp['kind'] in ('ALT', 'FINAL', 'NOISE', 'MIX') else 0.0
            for s in seeds:
                k = spec.get('k', 0.2) if t in spec.get('k_tasks', TASKS6) else spec.get('k_other', spec.get('k', 0.2))
                w = spec.get('w0', 0.4) - k * (q if sp['kind'] == 'ALT' else 0.0)                              # W_ind линейно падает с q у ALT
                if a == 'NOISE_50': w = (spec.get('w0', 0.4) - spec.get('k', 0.2) * 0.5) + spec.get('purge', 0.0) + (1 if s % 2 else -1) * spec.get('w_noise', 0.0)
                if a == 'FIX': w += spec.get('fix_bump', 0.0)                                                    # конец кривой вне прямой: внутренний наклон не должен его видеть
                tk = 0.5 + (0.1 if a == 'ALT_25' else 0.0) - (spec.get('mix_pen', 0.0) if a == 'MIX_25' else 0.0)
                tf = 0.5 - (0.3 if a == 'NOISE_50' else 0.0)
                mt = 0.3 + (0.1 if a == 'ALT_25' else 0.0) - (spec.get('final_pen', 0.0) if a == 'FINAL_25' else 0.0)
                bi = spec.get('b_i', 0.0) + (1 if s % 2 else -1) * spec.get('b_noise', 0.0)
                ser = {x: [9.0] * (GENS + 1) for x in SERIES}                                                   # мусор вне окна
                for g in range(121, 151):                                                                       # окно задано числами, независимо от LATE
                    ser['t_fix'][g] = tf; ser['c_fix'][g] = tf + w; ser['t_key'][g] = tk; ser['c_key'][g] = tk + 0.1
                    ser['c_eb'][g] = tk; ser['to_key'][g] = tk; ser['mT'][g] = mt; ser['mI'][g] = 0.1; ser['cm_key'][g] = tk; ser['uniq'][g] = 250
                kinds = ''.join(('M' if sp['kind'] == 'MIX' else (('N' if sp['kind'] == 'NOISE' else 'E') if is_exam(g, sp) else 'P')) for g in range(GENS + 1))
                grad = dict(bE_T=[77.0] * 31 + [2.0] * 120, bE_I=[77.0] * 31 + [bi * 2] * 120, sd_T=[0.5] * 151, sd_I=[0.5] * 151,     # β·sd: по правде 1,0; по завышению b_i
                            bP_T=[1.0] * 151, bP_I=[1.0] * 151, n1=[200] * 151)
                R[(t, a, s)] = dict(task=t, arm=a, seed=s, spec=sp, kinds=kinds, series=ser, labels_total=0, ignorance=0.5, deception=0.1, code='x', grad=grad,
                                    win={x: [9.0, 0.01, 0.01, 0.01, 0.01] for x in ('SP_T', 'SP_I', 'SE_T', 'SE_I', 'V_T', 'V_I', 'C_TI', 'rho_fix', 'rho_ex')})
    return R


def selftest():
    ok = []
    def chk(name, cond): ok.append(bool(cond)); print(('  ok  ' if cond else '  ОШИБКА  ') + name)
    A = analyze(synth())
    chk('P1a: наклон равен 0,2 и подтверждён', abs(A['P1a_dose_slope']['mean'] - 0.2) < 1e-6 and A['P1a_dose_slope']['verdict'] == 'подтверждено')
    chk('P1b: внутренний наклон тоже 0,2', abs(A['P1b_inner_slope']['mean'] - 0.2) < 1e-6 and A['P1b_inner_slope']['verdict'] == 'подтверждено')
    chk('P1: в проверке 20 сидов, пять задач без T1', A['P1a_dose_slope']['seeds'] == 20 and sorted(A['P1a_dose_slope']['by_task']) == list(TASKS_INFL))
    chk('P2: β_T на стандартное отклонение = 1,0 (поколения до 31 не входят)', abs(A['P2_exam_gradient_on_inflation']['beta_T_mean'] - 1.0) < 1e-9)
    chk('P3: разность правды 0,3 по шести задачам', abs(A['P3_truth_ALT50_vs_NOISE50']['mean'] - 0.3) < 1e-9 and sorted(A['P3_truth_ALT50_vs_NOISE50']['by_task']) == list(TASKS6))
    chk('P5: средняя правда популяции, ALT_25 − FINAL_25 = 0,1', abs(A['P5_popmean_truth_ALT25_vs_FINAL25']['mean'] - 0.1) < 1e-9 and A['P5_popmean_truth_ALT25_vs_FINAL25']['verdict'] == 'подтверждено')
    chk('сравнение с подмешиванием — без вердикта, разность 0,1', abs(A['D_truth_ALT25_vs_MIX25']['mean'] - 0.1) < 1e-9 and 'verdict' not in A['D_truth_ALT25_vs_MIX25'])
    chk('B1: разбавление даёт 0,5', abs(A['bets']['B1_excess_at_half_in_0.3_0.7']['value'] - 0.5) < 1e-6 and A['bets']['B1_excess_at_half_in_0.3_0.7']['holds'])
    chk('B2: вогнутость = 0,1', abs(A['bets']['B2_truth_concave']['value'] - 0.1) < 1e-9)
    chk('таблицы: W_ind FIX = 0,4, RND = 0,2; T_ind FIX = 0,5; T_key ALT_25 = 0,6; mT ALT_25 = 0,4',
        abs(A['tables']['W_ind']['FIX']['T3'] - 0.4) < 1e-9 and abs(A['tables']['W_ind']['RND']['T3'] - 0.2) < 1e-9 and abs(A['tables']['T_ind']['FIX']['T3'] - 0.5) < 1e-9
        and abs(A['tables']['T_key']['ALT_25']['T3'] - 0.6) < 1e-9 and abs(A['tables']['mT']['ALT_25']['T3'] - 0.4) < 1e-9)
    A = analyze(synth(spec=dict(b_i=0.3, b_noise=0.05)))
    chk('P2: β_I = 0,3 → «экзамен предпочитает завышенных»', A['P2_exam_gradient_on_inflation']['verdict'] == 'экзамен предпочитает завышенных' and abs(A['P2_exam_gradient_on_inflation']['mean'] - 0.3) < 1e-9)
    A = analyze(synth(spec=dict(b_i=-0.3, b_noise=0.05)))
    chk('P2: β_I = −0,3 → «экзамен чистит»', A['P2_exam_gradient_on_inflation']['verdict'] == 'экзамен чистит')
    A = analyze(synth(spec=dict(b_i=0.0, b_noise=0.03)))
    chk('P2: β_I около нуля, разброс мал → «экзамен слеп» (граница 0,1 от β_T)', A['P2_exam_gradient_on_inflation']['verdict'] == 'экзамен слеп' and abs(A['P2_exam_gradient_on_inflation']['blind_margin'] - 0.1) < 1e-9)
    A = analyze(synth(spec=dict(b_i=0.0, b_noise=0.9)))
    chk('P2: β_I около нуля, разброс велик → «не решено»', A['P2_exam_gradient_on_inflation']['verdict'] == 'не решено')
    A = analyze(synth(spec=dict(w_noise=0.02)))
    chk('P4: малый разброс вокруг нуля → «разницы нет»; узкая граница 0,02 тоже выполнена', A['P4_purge_NOISE50_minus_ALT50']['verdict'] == 'разницы нет' and A['P4_purge_NOISE50_minus_ALT50']['within_sens_margin'])
    A = analyze(synth(spec=dict(w_noise=0.07)))
    chk('P4: разброс 0,07 → «разницы нет» по 0,05, но узкая граница 0,02 не выполнена', A['P4_purge_NOISE50_minus_ALT50']['verdict'] == 'разницы нет' and not A['P4_purge_NOISE50_minus_ALT50']['within_sens_margin'])
    A = analyze(synth(spec=dict(w_noise=0.4)))
    chk('P4: большой разброс вокруг нуля → «не решено»', A['P4_purge_NOISE50_minus_ALT50']['verdict'] == 'не решено')
    A = analyze(synth(spec=dict(purge=0.1, w_noise=0.01)))
    chk('P4: NOISE выше ALT на 0,1 → «экзамен чистит»', A['P4_purge_NOISE50_minus_ALT50']['verdict'] == 'экзамен чистит' and abs(A['P4_purge_NOISE50_minus_ALT50']['mean'] - 0.1) < 1e-9)
    A = analyze(synth(spec=dict(purge=-0.1, w_noise=0.01)))
    chk('P4: NOISE ниже ALT на 0,1 → «обратный эффект»', A['P4_purge_NOISE50_minus_ALT50']['verdict'] == 'обратный эффект')
    A = analyze(synth(spec=dict(fix_bump=0.3)))
    chk('P1b: внутренний наклон не видит концов (0,2), общий — видит (больше 0,25)', abs(A['P1b_inner_slope']['mean'] - 0.2) < 1e-6 and A['P1a_dose_slope']['mean'] > 0.25)
    A = analyze(synth(spec=dict(k=-0.2)))
    chk('P1a: обратный наклон → «обратный эффект»', A['P1a_dose_slope']['verdict'] == 'обратный эффект')
    A = analyze(synth(spec=dict(k=1.0, k_tasks=('T2', 'T3'), k_other=-0.05)))
    chk('правило по задачам: эффект только в двух задачах из пяти → «в среднем, неоднородно по задачам»',
        A['P1a_dose_slope']['verdict'] == 'в среднем, неоднородно по задачам' and A['P1a_dose_slope']['tasks_positive'] == 2)
    A = analyze(synth(spec=dict(k=1.0, k_tasks=('T2', 'T3', 'T4', 'T5'), k_other=-0.05)))
    chk('правило по задачам: четыре задачи из пяти → «подтверждено»', A['P1a_dose_slope']['verdict'] == 'подтверждено' and A['P1a_dose_slope']['tasks_positive'] == 4)
    A = analyze(synth(spec=dict(final_pen=0.2)))
    chk('P5: штраф FINAL 0,2 → разность 0,3', abs(A['P5_popmean_truth_ALT25_vs_FINAL25']['mean'] - 0.3) < 1e-9)
    A = analyze(synth(spec=dict(mix_pen=0.3)))
    chk('сравнение с подмешиванием: штраф MIX 0,3 → разность 0,4', abs(A['D_truth_ALT25_vs_MIX25']['mean'] - 0.4) < 1e-9)
    A = analyze(synth(seeds=range(7)))
    chk('меньше 8 сидов → «n мало»', A['P1a_dose_slope']['verdict'] == 'n мало')
    import tempfile
    with tempfile.TemporaryDirectory() as d:                              # проверки целостности при чтении
        for k, j in list(synth(seeds=(1, 2)).items()):
            json.dump(j, open(os.path.join(d, f'{k[0]}_{k[1]}_s{k[2]}.json'), 'w'))
        try: load(d, expect_seeds=(1, 2)); chk('чтение: полный набор проходит', True)
        except AssertionError as e: chk(f'чтение: полный набор проходит ({e})', False)
        os.remove(os.path.join(d, 'T3_ALT_50_s1.json'))
        try: load(d, expect_seeds=(1, 2)); chk('чтение: нехватка прогона ловится', False)
        except AssertionError: chk('чтение: нехватка прогона ловится', True)
        j = synth(seeds=(1,))[('T3', 'ALT_50', 1)]; j['kinds'] = 'P' * (GENS + 1); json.dump(j, open(os.path.join(d, 'T3_ALT_50_s1.json'), 'w'))
        try: load(d, expect_seeds=(1, 2)); chk('чтение: неверное расписание ловится', False)
        except AssertionError: chk('чтение: неверное расписание ловится', True)
    print(f'самопроверка: {sum(ok)} из {len(ok)} пройдено')
    return all(ok)


VERDICTS = ('P1a_dose_slope', 'P1b_inner_slope', 'P2_exam_gradient_on_inflation', 'P3_truth_ALT50_vs_NOISE50', 'P4_purge_NOISE50_minus_ALT50', 'P5_popmean_truth_ALT25_vs_FINAL25')

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'selftest'
    if mode == 'selftest':
        sys.exit(0 if selftest() else 1)
    if mode == 'pilot':
        R = load(os.path.join(HERE, 'pilot'), expect_seeds=(990, 991, 992)); A = analyze(R)
        json.dump(A, open(os.path.join(HERE, 'pilot_results.json'), 'w'), ensure_ascii=False, indent=1)
    elif mode == 'test':
        assert selftest(), 'самопроверка не прошла'
        R = load(os.path.join(HERE, 'runs'), expect_seeds=tuple(range(100, 120))); A = analyze(R)
        json.dump(A, open(os.path.join(HERE, 'child01_results.json'), 'w'), ensure_ascii=False, indent=1)
    for k in VERDICTS + tuple(x for x in A if x.startswith('D_')):
        v = A[k]; print(k, v.get('verdict', '—'), 'среднее', v.get('mean'), 'интервал', v.get('ci95'), 'p', v.get('p_predicted'), 'сидов +/−', v.get('seeds_positive'), v.get('seeds_negative'),
                        'задач с плюсом', v.get('tasks_positive'), 'из', v.get('tasks_total'))
    for k, v in A['bets'].items(): print(' ', k, v)
    print('кривая доз W_ind:', A['dose_curve_W_ind']); print('кривая доз правды:', A['dose_curve_T_key'])
