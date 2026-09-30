# эталон ortools (120 с, 4 потока) и жадный контроль для dev и test; до прогона рук, результаты рук не используются
import sys, json, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import *
D = os.path.dirname(os.path.abspath(__file__)); out = {}
dst = '/root/solvers_secret/refs.json'
if os.path.exists(dst): out = json.load(open(dst))
for part in ('dev', 'test'):
    for inst in json.load(open(os.path.join(D, 'inst', f'{part}.json'))):
        k = f"{part}{inst['seed']}"
        if k in out: continue
        R = ortools_ref(inst, 120, 4); g = greedy(inst, 10, 0)
        out[k] = dict(ref=R['value'], bound=R['bound'], optimal=R['optimal'], greedy=g['value']); json.dump(out, open(dst, 'w'), indent=1); print(k, out[k], flush=True)
