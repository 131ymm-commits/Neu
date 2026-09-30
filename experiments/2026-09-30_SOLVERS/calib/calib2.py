import sys, json; sys.path.insert(0, '..')
from core import *
out = []
for seed in (9101, 9102, 9103, 9104):
    inst = gen_mkp(seed, 250, 6)
    gs = [greedy(inst, 10, s)['value'] for s in (0, 1, 2)]
    R = ortools_ref(inst, 120, 4)
    rec = dict(seed=seed, greedy_seeds=gs, ref=R['value'], bound=R['bound'], optimal=R['optimal']); out.append(rec); print(json.dumps(rec), flush=True)
json.dump(out, open('calib2.json', 'w'), indent=1)
