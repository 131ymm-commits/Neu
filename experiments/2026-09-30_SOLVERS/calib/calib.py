import sys, json, time; sys.path.insert(0, '..'); sys.path.insert(0, '.')
from core import *
out = []
cfg = [('MKP', dict(n=100, K=3)), ('MKP', dict(n=200, K=5)), ('MKP', dict(n=400, K=10)), ('MAXSAT', dict(n=80)), ('MAXSAT', dict(n=150)), ('MAXSAT', dict(n=600))]
for cls, kw in cfg:
    for seed in (9001, 9002):
        inst = gen_mkp(seed, **kw) if cls == 'MKP' else gen_maxsat(seed, **kw)
        g = greedy(inst, 10); R = ortools_ref(inst, 60, 4)
        rec = dict(cls=cls, **kw, seed=seed, greedy=g['value'], ref=R['value'], bound=R['bound'], optimal=R['optimal'])
        out.append(rec); print(json.dumps(rec), flush=True)
json.dump(out, open('calib/calib1.json', 'w'), indent=1)
