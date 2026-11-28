"""DEFER-01: числа отчёта из defer01_results.json (округления и производные), чтобы каждое число отчёта бралось из json.
python3 facts.py → facts.json"""
import json, math, os
H = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(H, 'defer01_results.json'))); D = R['EVO03_dose']; P = json.load(open(os.path.join(H, 'power.json')))
F = {}
for name, key in (('A', 'A_T2_M25_below_M0'), ('B', 'B_T3_slope_negative'), ('C', 'C_all_tasks_slope_negative')):
    v = D[key]
    F[name] = dict(verdict=v['verdict'], mean=round(v['mean'], 3), ci=[round(x, 3) for x in v['ci95']], p=v['p_predicted'],
                   seeds_for=v['seeds_positive'], seeds_against=v['seeds_negative'], seeds_zero=v['seeds'] - v['seeds_positive'] - v['seeds_negative'])
F['C_by_task'] = {t: dict(pos=x['pos'], neg=x['neg'], ties=x['ties'], mean=round(x['mean'], 3)) for t, x in D['C_all_tasks_slope_negative']['by_task'].items()}
F['W_by_task'] = {t: {a: round(x, 3) for a, x in v.items()} for t, v in D['desc_dose_means_by_task'].items()}
F['truth_by_task'] = {t: {a: round(x, 3) for a, x in v.items()} for t, v in D['desc_truth_means_by_task'].items()}
F['solved_by_task'] = D['desc_solved_share_by_task']; F['degenerate_by_task'] = D['desc_degenerate_share_by_task']
F['norm_slope'] = {t: D[f'desc_norm_slope_{t}'] for t in ('T1', 'T2', 'T3')}
F['T3_drop_at_max_dose_percent'] = round(100 * (1 - D['desc_norm_slope_T3']['ratios_to_M0']['MIRROR_100']))
F['pairs_M25_M0'] = {t: dict(pos=x['pos'], neg=x['neg'], ties=x['ties'], mean=round(x['mean'], 3)) for t, x in D['desc_M25_below_M0_by_task'].items()}
F['pairs_M100_M50'] = {t: dict(pos=x['pos'], neg=x['neg'], ties=x['ties'], mean=round(x['mean'], 3)) for t, x in D['desc_M100_below_M50_by_task'].items()}
for k in ('EVO01_FIXED16', 'EVO06_FIXED32'):
    f = R[k]; g = f['gap_growth']; t = f['truth_change']; s = f['seed_level_descriptive']
    F[k] = dict(grow=g['pos'], shrink=g['neg'], ties=g['ties'], changed=f['runs_with_change'], mean_growth=round(g['mean'], 3),
                seed_mean=round(s['mean'], 3), seed_ci=[round(x, 3) for x in s['ci95']], seed_p=round(s['p_predicted'], 5),
                truth_up=t['pos'], truth_down=t['neg'], truth_ties=t['ties'], late_share=f['truth_share_of_late_gain'], early_share=f['truth_share_of_early_gain'],
                late_gap_mean=round(f['late_gap']['mean'], 3), by_task={x: (v['pos'], v['neg'], v['ties']) for x, v in f['gap_growth_by_task'].items()})
for k in ('EVO01_RANDOM16', 'EVO06_SAME16', 'EVO06_SAME32'):
    g = R[k]['gap_growth']; F[k] = dict(grow=g['pos'], shrink=g['neg'], ties=g['ties'], late_gap_mean=round(R[k]['late_gap']['mean'], 4))
bets = [('A', 0.80, F['A']['verdict'] == 'подтверждено'), ('B', 0.60, F['B']['verdict'] == 'подтверждено'), ('C', 0.70, F['C']['verdict'] == 'подтверждено'),
        ('B1', 0.75, D['B1_T3_norm_slope_between_minus1_and_0']['holds']), ('B2', 0.55, D['B2_T1_M0_below_M25']['holds']),
        ('B3', 0.70, R['B3_FIXED16_gap_grows_in_majority']['holds']), ('B4', 0.75, R['B4_FIXED32_gap_grows_in_majority']['holds']),
        ('B5', 0.55, R['B5_SAME32_mean_gap']['holds']), ('B6', 0.15, R['B6_FIXED16_truth_declines_in_majority']['holds']),
        ('B7a', 0.60, R['B7a_FIXED32_late_gains_less_true_than_early']['holds']), ('B7b', 0.40, R['B7b_FIXED16_late_gains_less_true_than_early']['holds'])]
F['bets'] = [dict(id=i, p=p, outcome=int(bool(o))) for i, p, o in bets]
F['bets_summary'] = dict(n=len(bets), came_true=sum(int(bool(o)) for _, _, o in bets), brier=round(sum((p - bool(o)) ** 2 for _, p, o in bets) / len(bets), 3),
                         mean_probability=round(sum(p for _, p, _ in bets) / len(bets), 3), right_side=sum(int((p > 0.5) == bool(o)) for _, p, o in bets))
F['B3'] = R['B3_FIXED16_gap_grows_in_majority']; F['B4'] = R['B4_FIXED32_gap_grows_in_majority']
b5 = R['B5_SAME32_mean_gap']; F['B5'] = dict(mean16=round(b5['mean16'], 4), mean32=round(b5['mean32'], 4), ratio=b5['ratio'], ratio_unsolved=b5['ratio_both_unsolved'], pairs_unsolved=b5['pairs_both_unsolved'])
F['B6'] = R['B6_FIXED16_truth_declines_in_majority']
pw = dict(A=P['A_T2']['доля сидов с эффектом 0.7'][0], B=P['B_T3']['среднее 0.256'][0], C=P['C_all']['среднее 0.27'][0])
F['weights_bits'] = {k: round(math.log2(v / 0.005), 2) for k, v in pw.items()}; F['power'] = pw
F['pilot_vs_test'] = dict(T3_slope_pilot=0.256, T3_slope_test=F['B']['mean'], T2_share_seeds_with_effect=round(F['A']['seeds_for'] / 20, 2))
F['constants'] = dict(first_registration_commit_digits=6853317, b5_interval=[0.0083, 0.0167], population=300, tournament=5, late_window=[121, 150], seeds=20)   # постоянные из PREREG, чтобы аудит чисел их находил
json.dump(F, open(os.path.join(H, 'facts.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps({k: F[k] for k in ('A', 'B', 'C', 'bets_summary', 'weights_bits', 'T3_drop_at_max_dose_percent', 'B5')}, ensure_ascii=False))
