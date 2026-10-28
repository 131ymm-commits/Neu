#!/usr/bin/env python3
"""SELF-02: описательные числа отчёта из results_self_02.json → facts_self_02.json (вердикты не меняет;
записан после прогона 28.10.2026). Запуск из папки опыта: python3 report_facts_self02.py"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, 'results_self_02.json')))
S, T, O, OT, OB = range(5)
facts = {'part_B': {}, 'part_A': {}}
for arm in ('lin2_small', 'tanh2_small', 'lin2_lazy', 'lin1'):
    for q in (0.0, 0.5, 1.0):
        rs = sorted([r for r in d['B'] if r['arm'] == arm and r['q'] == q], key=lambda r: r['seed'])
        th = np.array([r['t_half'] for r in rs], float)
        facts['part_B'][f'{arm}_q{q}'] = dict(
            n=len(rs),
            med_t_self=float(np.median(th[:, S])), med_t_other=float(np.median(th[:, O])), med_t_object=float(np.median(th[:, OB])),
            med_rho_other=round(float(np.median(th[:, O] / th[:, S])), 3),
            med_rho_object=round(float(np.median(th[:, OB] / th[:, S])), 3),
            self_first=int((th[:, O] > th[:, S]).sum()), other_first=int((th[:, O] < th[:, S]).sum()),
            ties=int((th[:, O] == th[:, S]).sum()), object_after_other=int((th[:, OB] > th[:, O]).sum()),
            med_theory_other=round(float(np.median([r['rho_theory_other'] for r in rs])), 3),
            med_theory_object=round(float(np.median([r['rho_theory_object'] for r in rs])), 3),
            censored=int(sum(any(r['censored']) for r in rs)))
for q, k in ((0.0, 2), (0.5, 2), (1.0, 2), (1.0, 4)):
    rs = sorted([r for r in d['A'] if r['q'] == q and r['k'] == k], key=lambda r: r['seed'])
    m = np.array([r['mlp'] for r in rs])
    rr = np.array([r['rrr'] for r in rs])   # reduced-rank regression того же ранга (линейная теория горлышка)
    e = dict(n=len(rs), mean=np.round(m.mean(0), 2).tolist(), self_wins=int((m[:, S] > m[:, O]).sum()),
             same_as_s1=all(r['same_as_s1'] for r in rs), mean_mlp3=np.round(m.mean(0), 3).tolist(),
             mean_rrr3=np.round(rr.mean(0), 3).tolist(), max_abs_mean_mlp_minus_rrr=round(float(np.abs(m.mean(0) - rr.mean(0)).max()), 3))
    if q == 0.0:
        share = m[:, S] / (m[:, S] + m[:, O]); tot = m[:, S] + m[:, O]
        e.update(share_range=[round(float(share.min()), 3), round(float(share.max()), 3)], share_mean=round(float(share.mean()), 3),
                 sum_range=[round(float(tot.min()), 3), round(float(tot.max()), 3)])
    if k == 2 and q == 1.0:
        oo = np.array([r['ood'] for r in rs]); e['ood_mean'] = np.round(oo.mean(0), 2).tolist()
    facts['part_A'][f'q{q}_k{k}'] = e
s1 = json.load(open(os.path.join(HERE, '..', '2026-10-27_SELF-01', 'facts_self_01.json')))
facts['q0_self_wins_self01'] = s1['k2_q0.0']['self_wins']
facts['q0_self_wins_both'] = s1['k2_q0.0']['self_wins'] + facts['part_A']['q0.0_k2']['self_wins']
json.dump(facts, open(os.path.join(HERE, 'facts_self_02.json'), 'w'), ensure_ascii=False, indent=1)
for k, v in facts['part_B'].items():
    print(k, v)
for k, v in facts['part_A'].items():
    print(k, v)
print('q=0, SELF > OTHER: SELF-01', facts['q0_self_wins_self01'], '+ SELF-02', facts['part_A']['q0.0_k2']['self_wins'],
      '=', facts['q0_self_wins_both'], 'из 20')
