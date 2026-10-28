#!/usr/bin/env python3
"""TRUST-02: описательные числа отчёта из results_trust_02.json → facts_trust_02.json (вердикты не меняет;
записан после регистрации, до просмотра результатов). Запуск из папки опыта: python3 report_facts_trust02.py [папка, например pilot]"""
import json
import os
import sys

import numpy as np

import exp_trust_02 as E

DIR = os.path.join(E.HERE, sys.argv[1]) if len(sys.argv) > 1 else E.HERE     # папка с results (по умолчанию — опыт)
d = json.load(open(os.path.join(DIR, 'results_trust_02.json')))
th = d['theory']; seeds = d['params']['SEEDS']
R = {(r['seed'], r['arm']): r for r in d['runs']}
f = {'arms': {}, 'theory': {}, 'G_traj': {}}
for a, spec in E.ARMS.items():
    wk = spec['world']; rs = [R[(s, a)] for s in seeds]
    wex = np.array(th[wk]['w_exact'])
    def scl(r):
        w = E.WORLDS[wk].with_b(r['b_final'])
        return w.scale(r['w_final']) / w.scale(w.exact_weights() if wk == 'G' else wex)
    e = {k: round(float(np.mean([r['exact'][k] for r in rs])), 4) for k in ('self_dec', 'ignorance', 'ece', 'logloss', 'acc')}
    e.update(scale_ratio=round(float(np.mean([scl(r) for r in rs])), 3), neff=round(float(np.mean([r['neff_late'] for r in rs])), 1),
             sdF=round(float(np.median([r['sdF_late'] for r in rs])), 2),
             self_dec_snap=round(float(np.mean([r['self_dec_snap_mean'] for r in rs])), 4),
             excess_logloss_snap=round(float(np.mean([r['excess_logloss_snap_mean'] for r in rs])), 4),
             ece_snap=round(float(np.mean([r['ece_snap_mean'] for r in rs])), 4))
    if wk != 'G':
        e['shifted_self_dec'] = round(float(np.mean([r['exact_shifted']['self_dec'] for r in rs])), 4)
    else:
        e.update(b_final=round(float(np.mean([r['b_final'] for r in rs])), 4), b_sd_window=round(float(np.mean([r['b_sd_window'] for r in rs])), 4),
                 wG=round(float(np.mean([r['w_final'][1 + E.G_IDX] for r in rs])), 4))
    f['arms'][a] = e
for k in ('A', 'B', 'G'):
    t = th[k]
    f['theory'][k] = dict(exact_acc=round(t['exact_exact']['acc'], 4), exact_ignorance=round(t['exact_exact']['ignorance'], 4),
                          exact_logloss=round(t['exact_exact']['logloss'], 4), naive_self_dec=round(t['exact_naive']['self_dec'], 4),
                          naive_acc=round(t['exact_naive']['acc'], 4), ml_gap=round(t['max_abs_ml_minus_exact'], 4))
g = th['G']
f['theory']['G'].update(b_star=round(g['b_star'], 4), wG_star=round(g['wG_star'], 4), share_of_honest=round(g['wG_star'] / g['w_ref'], 3),
                        honest_formula_self_dec=round(g['exact_honest_formula_at_bstar']['self_dec'], 4),
                        honest_formula_acc=round(g['exact_honest_formula_at_bstar']['acc'], 4),
                        honest_formula_ignorance_excess=round(g['exact_honest_formula_at_bstar']['ignorance'] - g['exact_exact']['ignorance'], 4))
for a in ('KELLY_G', 'KELLY_GFIX'):
    tr = {}
    for gen in (0, 50, 100, 200, 400, 800, 1200, 1499):
        bs = [[t for t in R[(s, a)]['traj'] if t['g'] == gen][0] for s in seeds]
        tr[gen] = dict(b=round(float(np.mean([t['b'] for t in bs])), 4), wG=round(float(np.mean([t['w'][1 + E.G_IDX] for t in bs])), 4),
                       self_dec=round(float(np.mean([t['self_dec'] for t in bs])), 4),
                       excess_logloss=round(float(np.mean([t['logloss'] - t['logloss_bayes'] for t in bs])), 4))
    f['G_traj'][a] = tr
f['bits'] = dict(wG_star_bits=round(g['wG_star'] / np.log(2), 2), w_ref_bits=round(g['w_ref'] / np.log(2), 2),
                 wG_kelly_bits=round(f['arms']['KELLY_G']['wG'] / np.log(2), 2))
json.dump(f, open(os.path.join(DIR, 'facts_trust_02.json'), 'w'), ensure_ascii=False, indent=1)
for a, e in f['arms'].items():
    print(a, e)
print('теория', json.dumps(f['theory'], ensure_ascii=False))
for a, tr in f['G_traj'].items():
    print(a, ' '.join(f"{gg}: b {v['b']:.3f} w {v['wG']:.3f} sd {v['self_dec']:+.4f} xll {v['excess_logloss']:.4f}" for gg, v in tr.items()))
print('биты', f['bits'])
