# LEVEL-04, фаза 3: отбор in silico по настоящему ландшафту фазы 2 (PREREG: B = 100 ландшафтов × 50 зёрен, порог доли 0,8; sim.py не менялся, хеш в PREREG).
#   python3 phase3_run.py [phase2_landscape.json]  → phase3_results.json
import json, sys, os, hashlib
from sim import shares
HERE = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else f'{HERE}/phase2_landscape.json'
L = json.load(open(src)); land = L.get('landscape_with_rep') or L['landscape']   # по цепочкам и повторам, как в PREREG
C = json.load(open(f'{HERE}/phase0.json'))['C']
res = shares(land, C, seeds=50, B=100, seed=0)
out = dict(source=os.path.basename(src), sim_hash=hashlib.sha256(open(f'{HERE}/sim.py', 'rb').read()).hexdigest()[:16], C=C, seeds=50, B=100, seed=0, missing=L.get('missing', []), results=res)
json.dump(out, open(f'{HERE}/phase3_results.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
