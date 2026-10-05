# Подбор трудности 2 (после провала допуска на probe ред. 3): меньший лимит CPU и крупнее экземпляры; критерий допуска совета 24.
import json, sys, os, statistics as st
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import gen_mkp, greedy
import eco3
pop = eco3.J(eco3.SP)['pop']
CONF = [(2000, 20, 0.5, 'strong'), (5000, 50, 0.5, 'strong'), (3000, 30, 0.3, 'weak'), (10000, 20, 0.5, 'weak')]
res = []
for cpu in (1, 3):
    eco3.CPU = cpu
    for ci, (n, K, t, c) in enumerate(CONF):
        I = [gen_mkp(920000 + 100 * ci + j, n, K, t, c) for j in range(2)]
        for x in I: x['klass'] = 0
        R = eco3.eval_many([(p['code'], x, x['seed']) for p in pop for x in I]); G = [greedy(x, cpu, 0)['value'] for x in I]
        for j in range(2):
            col = [R[k * 2 + j][0] for k in range(len(pop))]; ok = [v for v in col if v is not None]
            d = 0.0002 * G[j]
            r = dict(cpu=cpu, conf=(n, K, t, c), greedy=G[j], fails=len(col) - len(ok), distinct=len(set(ok)), spread=(max(ok) - min(ok)) if ok else 0,
                     gap_med=(max(ok) - st.median(ok)) if ok else 0, delta_floor=round(d, 1), best_minus_greedy=(max(ok) - G[j]) if ok else 0)
            r['admit'] = r['distinct'] >= 3 and r['spread'] > d and r['gap_med'] > d; res.append(r); print(r, flush=True)
json.dump(res, open('eco/hardness_scan2.json', 'w'), indent=1)
