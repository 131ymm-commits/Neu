"""CHILD-01: числа отчёта из child01_results.json (округления и производные), чтобы каждое число отчёта бралось из json.
  python3 facts.py [pilot|test] → facts.json (для pilot — facts_pilot.json)"""
import glob, json, math, os, sys
import numpy as np
H = os.path.dirname(os.path.abspath(__file__)); mode = sys.argv[1] if len(sys.argv) > 1 else 'test'
R = json.load(open(os.path.join(H, 'pilot_results.json' if mode == 'pilot' else 'child01_results.json')))
P = json.load(open(os.path.join(H, 'power.json'))); FI = json.load(open(os.path.join(H, 'fi_curves.json')))
r3 = lambda x: None if x is None else round(float(x), 3)
F = dict(runs=R['runs'], seeds=len(R['seeds']), seed_first=R['seeds'][0], seed_last=R['seeds'][-1])
def block(v):
    d = dict(verdict=v.get('verdict'), mean=r3(v.get('mean')), ci=None if v.get('ci95') is None else [r3(x) for x in v['ci95']], p_up=v.get('p_predicted'), p_down=v.get('p_opposite'),
             seeds_plus=v.get('seeds_positive'), seeds_minus=v.get('seeds_negative'), tasks_plus=v.get('tasks_positive'), tasks_total=v.get('tasks_total'),
             by_task={t: dict(plus=x['pos'], minus=x['neg'], ties=x['ties'], mean=r3(x['mean'])) for t, x in v.get('by_task', {}).items()})
    if d['seeds_plus'] is not None: d['seeds_zero'] = v['seeds'] - d['seeds_plus'] - d['seeds_minus']
    for k in ('beta_T_mean', 'blind_margin', 'within_sens_margin'):
        if k in v: d[k] = r3(v[k]) if not isinstance(v[k], bool) else v[k]
    return d
for k, v in R.items():
    if k[:2] in ('P1', 'P2', 'P3', 'P4', 'P5') or k.startswith('D_'): F[k] = block(v)
# после совета 49: P1b и P2 по PREREG §4 — описательные меры без вердикта; ярлык, который выдаёт код анализа, вердиктом не является
for k in ('P1b_inner_slope', 'P2_exam_gradient_on_inflation'):
    F[k]['analysis_label'] = F[k]['verdict']; F[k]['verdict'] = None; F[k]['status'] = 'описательная мера, без вердикта и веса (PREREG §4, правило мощности)'
F['dose_W_ind'] = {a: r3(x) for a, x in R['dose_curve_W_ind'].items()}; F['dose_T_key'] = {a: r3(x) for a, x in R['dose_curve_T_key'].items()}
w0, w1 = R['dose_curve_W_ind']['FIX'], R['dose_curve_W_ind']['RND']
F['excess_share'] = {a: r3((x - w1) / (w0 - w1)) for a, x in R['dose_curve_W_ind'].items()} if abs(w0 - w1) > 1e-9 else None
F['tables'] = {n: {a: {t: r3(x) for t, x in row.items()} for a, row in tab.items()} for n, tab in R['tables'].items()}
F['solved_share'] = R['solved_share']; F['labels_per_run'] = R['labels_per_run']
# среднее завышение показателя по задачам T2–T6 для всех ветвей (в кривой доз оно уже есть; здесь — и для контролей); добавлено до конца теста
F['W_ind_T2_T6'] = {a: r3(np.mean([row[t] for t in ('T2', 'T3', 'T4', 'T5', 'T6')])) for a, row in R['tables']['W_ind'].items()}
F['bits_per_label'] = None
# ставки и калибровка
V = lambda k: R[k].get('verdict')
bets = [('P1', 0.80, V('P1a_dose_slope') == 'подтверждено'), ('P3', 0.85, V('P3_truth_ALT50_vs_NOISE50') == 'подтверждено'),
        ('P4 не «чистит»', 0.95, V('P4_purge_NOISE50_minus_ALT50') != 'экзамен чистит'), ('P5', 0.40, V('P5_popmean_truth_ALT25_vs_FINAL25') == 'подтверждено'),
        ('P1b знак', 0.70, R['P1b_inner_slope']['mean'] > 0), ('P2 знак', 0.70, R['P2_exam_gradient_on_inflation']['mean'] < 0)]
pb = dict(B1=0.60, B2=0.65, B3=0.50, B4=0.60, B5=0.65, B6a=0.60, B6b=0.80, B7=0.60, B8=0.40, B9=0.50)
for k, v in R['bets'].items(): bets.append((k.split('_')[0], pb[k.split('_')[0]], bool(v['holds'])))
bets.append(('B10', 0.60, R['D_truth_ALT25_vs_MIX25']['mean'] > 0))
F['bets'] = [dict(id=i, p=p, outcome=int(bool(o))) for i, p, o in bets]; F['bets_values'] = {k: v['value'] for k, v in R['bets'].items()}
F['bets_summary'] = dict(n=len(bets), came_true=sum(int(bool(o)) for _, _, o in bets), brier=round(sum((p - bool(o)) ** 2 for _, p, o in bets) / len(bets), 3),
                         mean_probability=round(sum(p for _, p, _ in bets) / len(bets), 3), right_side=sum(int((p > 0.5) == bool(o)) for _, p, o in bets if p != 0.5),
                         not_half=sum(1 for _, p, _ in bets if p != 0.5))
# веса опоры по правилу PREREG §3
pw = dict(P1=P['P1a_dose_slope']['главный: эффект пилота, разброс ×3']['confirmed'], P3=P['P3_truth_ALT50_vs_NOISE50']['главный: эффект пилота, разброс ×3']['confirmed'],
          P5=P['P5_popmean_truth_ALT25_vs_FINAL25']['главный: эффект пилота, разброс ×3']['confirmed'])
F['power'] = pw; F['weights_if_confirmed'] = {k: round(math.log2(v / 0.005), 2) for k, v in pw.items()}
F['weights_if_undecided'] = {k: round(math.log2((1 - v) / 0.995), 2) for k, v in pw.items()}
p4 = P['P4_purge_NOISE50_minus_ALT50']
F['weights_P4'] = dict(no_difference=round(math.log2(p4['разницы нет, разброс ×3']['same'] / p4['экзамен чистит на 0,05, разброс ×3']['same']), 2),
                       cleans=round(math.log2(p4['экзамен чистит на 0,05, разброс ×3']['up'] / p4['разницы нет, разброс ×3']['up']), 2),
                       reverse=round(math.log2(p4['главный: как в пилоте, разброс ×3']['down'] / p4['разницы нет, разброс ×3']['down']), 2))
# функциональная информация: медиана бит правды и заявки рабочей элиты (поздние поколения) там, где кривая известна
folder = os.path.join(H, 'pilot' if mode == 'pilot' else 'runs'); LIM = round(-math.log2(3 / FI['direct']['T1_D6']['M']), 2)
def bits(task, x):
    lf = FI['direct'][f'{task}_D6']['logF']; k = int(round(min(1.0, max(0.0, x)) * 201)); return None if lf[k] is None else -lf[k]
fi = {}
for f in glob.glob(os.path.join(folder, '*.json')):
    j = json.load(open(f))
    if j['arm'] not in ('FIX', 'ALT_25', 'RND'): continue
    s = j['series']; t = float(np.mean(s['t_key'][121:151])); c = float(np.mean(s['c_key'][121:151]))
    fi.setdefault((j['task'], j['arm']), []).append((bits(j['task'], t), bits(j['task'], c)))
F['fi_bits'] = {}
for (task, arm), v in sorted(fi.items()):
    bt = [LIM + 1 if x[0] is None else x[0] for x in v]; bc = [LIM + 1 if x[1] is None else x[1] for x in v]      # уровни за пределом счёта — как «больше предела»
    mt, mc = float(np.median(bt)), float(np.median(bc))
    F['fi_bits'][f'{task}_{arm}'] = dict(truth_bits_median=None if mt > LIM else round(mt, 1), claim_bits_median=None if mc > LIM else round(mc, 1),
                                         share_truth_beyond_limit=round(float(np.mean([x[0] is None for x in v])), 2), share_claim_beyond_limit=round(float(np.mean([x[1] is None for x in v])), 2))
F['fi_limit_bits'] = LIM
# производные числа текста отчёта (добавлено после теста, только арифметика над уже посчитанным)
wm = lambda a: float(np.mean([R['tables']['W_ind'][a][t] for t in ('T2', 'T3', 'T4', 'T5', 'T6')]))
F['derived'] = dict(inflation_drop_half_exam=r3(wm('FIX') - wm('ALT_50')), inflation_drop_half_noise=r3(wm('FIX') - wm('NOISE_50')),
                    ceiling_room_NOISE_50=r3(1 - R['tables']['T_ind']['NOISE_50']['mean']), ceiling_room_ALT_50=r3(1 - R['tables']['T_ind']['ALT_50']['mean']))
# ложный уровень: направленные вердикты (4 проверки × 2 стороны × 0,005) и отдельно ошибка вердикта «разницы нет» при чистке 0,05 (power.json)
F['family_error'] = dict(directional=0.04, equivalence_if_purge_0_05=P['P4_purge_NOISE50_minus_ALT50']['экзамен чистит на 0,05, разброс ×3']['same'],
                         equivalence_if_no_difference=P['P4_purge_NOISE50_minus_ALT50']['разницы нет, разброс ×3']['same'])
if mode == 'test':
    RP = json.load(open(os.path.join(H, 'pilot_results.json')))
    F['derived']['P5_pilot_over_test'] = round(RP['P5_popmean_truth_ALT25_vs_FINAL25']['mean'] / R['P5_popmean_truth_ALT25_vs_FINAL25']['mean'], 1)
F['constants'] = dict(population=300, generations=150, tournament=5, tests=16, tasks=6, arms=15, late_window=[121, 150], hidden=1000, outside=400, alpha_side=0.005, eq_margin=0.05, eq_sens=0.02,
                      pilot_seeds=[990, 991, 992], registration_digits=84459, council=48, selftest=29, mutants=26, family_error=0.04)
json.dump(F, open(os.path.join(H, 'facts_pilot.json' if mode == 'pilot' else 'facts.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for k in ('P1a_dose_slope', 'P1b_inner_slope', 'P2_exam_gradient_on_inflation', 'P3_truth_ALT50_vs_NOISE50', 'P4_purge_NOISE50_minus_ALT50', 'P5_popmean_truth_ALT25_vs_FINAL25'):
    v = F[k]; print(k, v['verdict'], v['mean'], v['ci'], v['p_up'], v['seeds_plus'], v['seeds_minus'], v['tasks_plus'], v['tasks_total'])
print(F['bets_summary']); print(F['dose_W_ind']); print(F['dose_T_key'])
