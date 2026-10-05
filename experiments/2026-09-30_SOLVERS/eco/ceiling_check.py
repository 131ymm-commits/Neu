# Проверка потолка до пилота: значения решателей поколения 0 по экземплярам калибровочного набора при 10 с и 2 с CPU против эталона ortools.
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import ortools_ref
from eco_sets import inst as mk
from eco import eval_many, J
s = J('eco/pilot/state.json'); cal = J('eco/calib_set.json'); CI = [mk(c['seed'], c['klass']) for c in cal]
pop = s['pop']
out = {'greedy': [c['greedy'] for c in cal]}
for cpu in (10, 2):
    import eco; eco.CPU = cpu
    R = eval_many([(p['code'], I, I['seed']) for p in pop for I in CI])
    for k, p in enumerate(pop): out[f"{p['id']}@{cpu}"] = [r[0] for r in R[k * len(CI):(k + 1) * len(CI)]]
out['ref'] = []
for I in CI:
    r = ortools_ref(I, 30, 4); out['ref'].append([r['value'], r['bound'], r['optimal']])
json.dump(out, open('eco/ceiling_check.json', 'w'), indent=1)
ref = [r[0] for r in out['ref']]
for k, v in out.items():
    if k in ('ref',): continue
    print(k, [None if x is None else ref[i] - x for i, x in enumerate(v)])
print('ref', out['ref'])
