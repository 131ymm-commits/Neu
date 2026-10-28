"""SELF-01: числа отчёта из exp_self_01_results.json → facts_self_01.json (округление как в отчёте).
Запуск из папки опыта: python3 report_facts_self01.py"""
import json
import numpy as np

d = json.load(open('exp_self_01_results.json'))
fits, curves, spec = d['fits'], d['curves'], d['spectrum']
names = d['names']


def sel(q, k):
    return [r for r in fits if r['q'] == q and r['k'] == k]


facts = {'gap': {q: round(spec[q]['gap'], 3) for q in spec},
         'eig_top3': {q: spec[q]['eig'][:3] for q in spec}}
for q in (0.0, 0.5, 1.0):
    rows = sel(q, 2)
    mlp = np.array([r['mlp'] for r in rows]); rrr = np.array([r['rrr'] for r in rows])
    facts[f'k2_q{q}'] = {
        'n': len(rows),
        'mean_mlp': dict(zip(names, np.round(mlp.mean(0), 2).tolist())),
        'mean_rrr': dict(zip(names, np.round(rrr.mean(0), 2).tolist())),
        'self_wins': int((mlp[:, 0] > mlp[:, 2]).sum()),
        'self_range_mlp': [round(float(mlp[:, 0].min()), 2), round(float(mlp[:, 0].max()), 2)],
        'share_self_range_mlp': [round(float((mlp[:, 0] / (mlp[:, 0] + mlp[:, 2])).min()), 2),
                                 round(float((mlp[:, 0] / (mlp[:, 0] + mlp[:, 2])).max()), 2)],  # доля SELF/(SELF+OTHER)
        'self_plus_other_mlp': np.round(mlp[:, 0] + mlp[:, 2], 2).tolist(),
        'max_abs_mlp_minus_rrr_self': round(float(np.abs(mlp[:, 0] - rrr[:, 0]).max()), 2),
    }
ladder = {}
for q in (0.0, 0.5, 1.0):
    for k in (1, 2, 3, 4, 6, 8, 16):
        rows = sel(q, k)
        m = np.mean([r['mlp'] for r in rows], 0); r_ = np.mean([r['rrr'] for r in rows], 0)
        ladder[f'q{q}_k{k}'] = {'mlp': np.round(m, 2).tolist(), 'rrr': np.round(r_, 2).tolist(),
                                'max_abs_mean_diff': round(float(np.abs(m - r_).max()), 2)}
facts['ladder'] = ladder
facts['max_abs_mean_diff_all'] = max(v['max_abs_mean_diff'] for v in ladder.values())
facts['curves'] = [{'q': c['q'], 'seed': c['seed'], 't80': c['t80']} for c in curves]
json.dump(facts, open('facts_self_01.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: facts[k] for k in facts if k.startswith('k2') or k in ('gap', 'max_abs_mean_diff_all')}, ensure_ascii=False, indent=1))
