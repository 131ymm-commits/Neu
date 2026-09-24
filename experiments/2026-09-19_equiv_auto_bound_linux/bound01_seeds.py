# BOUND-01, проверка устойчивости по сидам (post hoc, после основного прогона)
import json, numpy as np, bound01 as b
truth = {'S1': 'порядок', 'S2': 'порядок', 'S3': 'край', 'S4': 'хаос', 'S5': 'хаос'}
out = {}
for sy in truth:
    rows = []
    for seed in range(1, 11):
        a = b.run(sy, 16, 64, 400, 0.01, seed=seed); c = b.run(sy, 64, 64, 400, 0.01, seed=seed)
        v = b.classify(a['N'], c['N'] - a['N'])
        rows.append((a['N'], c['N'], v))
    ok = sum(r[2] == truth[sy] for r in rows)
    out[sy] = dict(correct=ok, rows=rows)
    print(sy, truth[sy], 'верно', ok, 'из 10', [r[:2] for r in rows], flush=True)
json.dump(out, open('bound01_seeds.json', 'w'), ensure_ascii=False, indent=1)
