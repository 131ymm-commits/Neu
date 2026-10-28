#!/usr/bin/env python3
"""TRUST-02: вердикты и сводные исходы по букве PREREG-TRUST-02.md §4 из results_trust_02.json →
analysis_trust_02.json (рядом с входным файлом). Запуск: python3 analyze_trust_02.py [путь к results]."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exp_trust_02 as E  # noqa: E402

src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'results_trust_02.json')
d = json.load(open(src))
th = d['theory']
seeds = d['params']['SEEDS']
NS = len(seeds)
R = {(r['seed'], r['arm']): r for r in d['runs']}
assert len(R) == NS * len(E.ARMS) and all((s, a) in R for s in seeds for a in E.ARMS), 'неполные ячейки'
for k in ('A', 'B', 'G'):                                   # второй способ теории (PREREG §2)
    assert th[k]['max_abs_ml_minus_exact'] <= 0.025, ('ML далеко от точных весов', k)
for r in d['runs']:                                        # второй способ оценки (PREREG §2)
    assert abs(r['exact']['self_dec'] - r['test']['self_dec']) <= 0.003, ('способы оценки расходятся', r['seed'], r['arm'])


def boot_ci(x, B=10000, seed=0):
    x = np.asarray(x, float); g = np.random.default_rng(seed)
    m = x[g.integers(0, len(x), (B, len(x)))].mean(1)
    return [float(x.mean()), float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


def sign_outcome(count, k):
    """Счётное «в ≥ k из 10»: подтверждено при count ≥ k, опровергнуто при count ≤ 10 − k, иначе не показано."""
    return 'подтверждено' if count >= k else ('опровергнуто' if count <= NS - k else 'не показано')


def interval(ok):
    return 'подтверждено' if ok else 'не подтверждено'


WB, WG = E.WB, E.WG
wB = np.array(th['B']['w_exact']); idB = WB.identifiable(wB); scB = WB.scale(wB)
nvB = np.array(th['B']['identifiable_naive'])
b_star = th['G']['b_star']; W_REF = th['G']['w_ref']
rows = {}
for s in seeds:
    kb, ib, lb = R[(s, 'KELLY_B')], R[(s, 'INDEP_B')], R[(s, 'KLUCK_B')]
    idf = WB.identifiable(kb['w_final'])
    kg = R[(s, 'KELLY_G')]; wgb = WG.with_b(kg['b_final'])
    wG = kg['w_final'][1 + E.G_IDX]; wG_bayes = wgb.exact_weights()[1 + E.G_IDX]
    rows[s] = dict(
        mad_B=float(np.abs(idf - idB).mean()), scale_B=WB.scale(kb['w_final']) / scB, sd_B=kb['exact']['self_dec'],
        pair1=float(idf[3]), pair2=float(idf[4]), w0dev_B=float(abs(idf[0] - idB[0])),
        sd_INDEP_B=ib['exact']['self_dec'], scale_INDEP_B=WB.scale(ib['w_final']) / scB,
        sd_KLUCK_B=lb['exact']['self_dec'], neff_INDEP_B=ib['neff_late'], neff_KLUCK_B=lb['neff_late'],
        acc_KELLY_B=kb['exact']['acc'], acc_INDEP_B=ib['exact']['acc'], acc_KLUCK_B=lb['exact']['acc'],
        sd_KELLY_A=R[(s, 'KELLY_A')]['exact']['self_dec'], sd_CONTEST_A=R[(s, 'CONTEST_A')]['exact']['self_dec'],
        sd_KELLY6_A=R[(s, 'KELLY6_A')]['exact']['self_dec'],
        rho1=float((idf[3] / idB[3]) / (np.linalg.norm(idf[1:3]) / np.linalg.norm(idB[1:3]))),
        rho2=float((idf[4] / idB[4]) / (np.linalg.norm(idf[1:3]) / np.linalg.norm(idB[1:3]))),
        xll_G=kg['excess_logloss_snap_mean'], ece_G=kg['ece_snap_mean'], b_sd_G=kg['b_sd_window'],
        xll_GFIX=R[(s, 'KELLY_GFIX')]['excess_logloss_snap_mean'], sd_snap_GFIX=R[(s, 'KELLY_GFIX')]['self_dec_snap_mean'],
        wG_GFIX=R[(s, 'KELLY_GFIX')]['w_final'][1 + E.G_IDX],
        sd_CONTEST400_A=R[(s, 'CONTEST400_A')]['exact']['self_dec'],
        wG=float(wG), wG_bayes=float(wG_bayes), b_final=kg['b_final'], sd_snap_G=kg['self_dec_snap_mean'],
        sd_snap_A=R[(s, 'KELLY_A')]['self_dec_snap_mean'], acc_G=kg['exact']['acc'],
        acc_G_bayes=wgb.exact_metrics(wgb.exact_weights())['acc'],
        mad_G=float(np.abs(wgb.identifiable(kg['w_final']) - wgb.identifiable(wgb.exact_weights())).mean()))
col = lambda k: [rows[s][k] for s in seeds]
V = {}
# --- часть R: повтор на мире B ---
c_sc = sum(0.9 <= x <= 1.2 for x in col('scale_B')); c_cal = sum(abs(x) <= 0.015 for x in col('sd_B'))
V['R1'] = dict(ok=bool(np.mean(col('mad_B')) <= 0.25 and c_sc >= 9 and c_cal >= 9), mad=boot_ci(col('mad_B')),
               scale_in=c_sc, calibrated=c_cal, scale=boot_ci(col('scale_B')), sd=boot_ci(col('sd_B')))
# R3 (после проверки по трём линзам — относительная форма): ρ_p = (сумма пары / точная) / (масштаб одиночных / точный);
# у точной формулы ρ = 1, у наивной при любом общем множителе — naive/exact; кромка — середина между ними
rk1, rk2 = (1 + nvB[3] / idB[3]) / 2, (1 + nvB[4] / idB[4]) / 2
c3 = sum(rows[s]['rho1'] <= rk1 and rows[s]['rho2'] <= rk2 for s in seeds)
V['R3'] = dict(ok=c3 >= 9, n=c3, edge1=float(rk1), edge2=float(rk2), rho1=boot_ci(col('rho1')), rho2=boot_ci(col('rho2')),
               naive_rho=[float(nvB[3] / idB[3]), float(nvB[4] / idB[4])], pair1=boot_ci(col('pair1')), pair2=boot_ci(col('pair2')))
c4 = sum(x <= 0.4 for x in col('w0dev_B'))
V['R4'] = dict(ok=c4 >= 9, n=c4, w0dev=boot_ci(col('w0dev_B')))
c5 = sum(rows[s]['sd_INDEP_B'] >= 0.015 and rows[s]['scale_INDEP_B'] >= 1.5 for s in seeds)
V['R5'] = dict(ok=c5 >= 9, n=c5, outcome=sign_outcome(c5, 9), sd=boot_ci(col('sd_INDEP_B')), scale=boot_ci(col('scale_INDEP_B')))
c6 = sum(abs(x) <= 0.015 for x in col('sd_KLUCK_B'))
nratio = float(np.median([rows[s]['neff_KLUCK_B'] / rows[s]['neff_INDEP_B'] for s in seeds]))
V['R6'] = dict(ok=bool(c6 >= 9 and 0.5 <= nratio <= 2.0), calibrated=c6, neff_ratio=nratio, sd=boot_ci(col('sd_KLUCK_B')))
gap = {a: float(np.mean([abs(rows[s][f'acc_{a}'] - rows[s]['acc_KELLY_B']) for s in seeds])) for a in ('INDEP_B', 'KLUCK_B')}
V['R7'] = dict(ok=all(v <= 0.005 for v in gap.values()), gap=gap)
# --- часть M: турнир и малая выборка (мир A) ---
c_m1 = sum(rows[s]['sd_CONTEST_A'] > rows[s]['sd_KELLY6_A'] for s in seeds)     # как T9 TRUST-01: против KELLY6
V['M1'] = dict(ok=c_m1 >= 8, n=c_m1, outcome=sign_outcome(c_m1, 8),     # ≥ 8 из 10 — по калибровке пилота на 5 зёрнах
               diff=boot_ci([rows[s]['sd_CONTEST_A'] - rows[s]['sd_KELLY6_A'] for s in seeds]),
               diff_vs_kelly=boot_ci([rows[s]['sd_CONTEST_A'] - rows[s]['sd_KELLY_A'] for s in seeds]),
               diff_kelly6_kelly=boot_ci([rows[s]['sd_KELLY6_A'] - rows[s]['sd_KELLY_A'] for s in seeds]))
c_m2 = sum(rows[s]['sd_CONTEST400_A'] < rows[s]['sd_CONTEST_A'] for s in seeds)
m40, m400 = float(np.mean(col('sd_CONTEST_A'))), float(np.mean(col('sd_CONTEST400_A')))
V['M2'] = dict(ok=bool(c_m2 >= 9 and m400 <= 0.5 * m40), n=c_m2, count_outcome=sign_outcome(c_m2, 9),
               sd_L40=boot_ci(col('sd_CONTEST_A')), sd_L400=boot_ci(col('sd_CONTEST400_A')), ratio=m400 / m40 if m40 else None,
               sd_KELLY_A=boot_ci(col('sd_KELLY_A')))
# --- часть G: источник с интересом ---
c_g1 = sum(rows[s]['wG'] <= 0.75 * W_REF and abs(rows[s]['wG'] - rows[s]['wG_bayes']) <= 0.2 for s in seeds)
V['G1'] = dict(ok=c_g1 >= 9, n=c_g1, wG=boot_ci(col('wG')), wG_bayes=boot_ci(col('wG_bayes')), w_ref=W_REF,
               wG_star=th['G']['wG_star'], share_of_honest=float(np.mean(col('wG')) / W_REF))
# G2 — описательно (после проверки по трём линзам: b_final линейно зависит от w̄_G, это та же проверка, что G1)
DESC = dict(b_final=boot_ci(col('b_final')), b_star=b_star, b_sd_window=boot_ci(col('b_sd_G')),
            n_b_within_005=int(sum(abs(x - b_star) <= 0.05 for x in col('b_final'))),
            wG_GFIX=boot_ci(col('wG_GFIX')), sd_snap_G=boot_ci(col('sd_snap_G')), sd_snap_GFIX=boot_ci(col('sd_snap_GFIX')),
            ece_G=boot_ci(col('ece_G')), acc_G=boot_ci(col('acc_G')), acc_G_bayes=boot_ci(col('acc_G_bayes')),
            mad_G=boot_ci(col('mad_G')))
# G3 — избыток лог-потери над байесовской формулой при своём b, среднее по снимкам окна
c_g3 = sum(x <= 0.012 for x in col('xll_G'))
V['G3'] = dict(ok=c_g3 >= 9, n=c_g3, excess_logloss=boot_ci(col('xll_G')))
# G4 (разведка): отклик источника на репутацию даёт лёгкую самоуверенность — KELLY_G против KELLY_GFIX (тот же мир, b = b*)
c_g4 = sum(rows[s]['sd_snap_G'] > rows[s]['sd_snap_GFIX'] for s in seeds)
V['G4'] = dict(ok=c_g4 >= 7, n=c_g4, outcome=sign_outcome(c_g4, 7),
               diff=boot_ci([rows[s]['sd_snap_G'] - rows[s]['sd_snap_GFIX'] for s in seeds]),
               diff_excess_logloss=boot_ci([rows[s]['xll_G'] - rows[s]['xll_GFIX'] for s in seeds]))
for k in ('R1', 'R3', 'R4', 'R6', 'R7', 'G1', 'G3'):
    V[k]['outcome'] = interval(V[k]['ok'])
V['M2']['outcome'] = interval(V['M2']['ok'])
# --- сводные исходы (PREREG §4) ---
if V['R1']['ok'] and V['R5']['ok'] and V['R6']['ok']:
    thesis = 'подтверждено'
elif (sum(x >= 0.015 for x in col('sd_INDEP_B')) <= 2 or sum(abs(x) > 0.02 for x in col('sd_B')) >= 5
      or sum(abs(x) > 0.02 for x in col('sd_KLUCK_B')) >= 5):
    thesis = 'опровергнуто'
else:
    thesis = 'не подтверждено'
if V['M1']['ok'] and V['M2']['ok']:
    tour = 'подтверждено'
elif m400 >= 0.8 * m40 or c_m2 <= 5:
    tour = 'опровергнуто'
else:
    tour = 'не подтверждено'
if V['G1']['ok'] and V['G3']['ok']:
    goodhart = 'подтверждено'
elif sum(x > 0.02 for x in col('xll_G')) >= 5 or sum(x > 0.9 * W_REF for x in col('wG')) >= 5:
    goodhart = 'опровергнуто'
else:
    goodhart = 'не подтверждено'
summary = dict(thesis_risk_structure_B=thesis, tournament_small_sample=tour, interested_source_withstood=goodhart)
out = dict(verdicts=V, summary=summary, descriptive_G=DESC, rows={str(s): rows[s] for s in seeds}, n_seeds=NS,
           dry=('dry' in os.path.dirname(os.path.abspath(src)) or 'pilot' in os.path.dirname(os.path.abspath(src))),
           theory={k: dict(max_abs_ml_minus_exact=th[k]['max_abs_ml_minus_exact'], exact_acc=th[k]['exact_exact']['acc'],
                           naive_self_dec=th[k]['exact_naive']['self_dec'], naive_acc=th[k]['exact_naive']['acc'])
                   for k in ('A', 'B', 'G')},
           second_method_max_gap_self_dec=max(abs(r['exact']['self_dec'] - r['test']['self_dec']) for r in d['runs']))
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(src)), 'analysis_trust_02.json'), 'w'),
          ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
for k, v in V.items():
    print(k, '✓' if v['ok'] else '✗', v['outcome'], {kk: (np.round(vv, 4).tolist() if isinstance(vv, list) else
                                                         (round(vv, 4) if isinstance(vv, float) else vv))
                                                    for kk, vv in v.items() if kk not in ('ok', 'outcome')})
print('сводные исходы:', summary)
