# Подбор трудности корма: где решатели поколения 0 расходятся (разброс значений), при 10 с CPU.
import json, sys, os, statistics as st
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import gen_mkp, greedy
from eco import eval_many, J
pop = J('eco/pilot/state.json')['pop']
CONF = [dict(n=1000, K=10, tight=0.5, corr='strong'), dict(n=2000, K=20, tight=0.5, corr='strong'), dict(n=3000, K=30, tight=0.3, corr='weak'), dict(n=600, K=40, tight=0.6, corr='strong')]
res = {}
for ci, c in enumerate(CONF):
    I = [gen_mkp(910000 + 100 * ci + j, c['n'], c['K'], c['tight'], c['corr']) for j in range(2)]
    R = eval_many([(p['code'], x, x['seed']) for p in pop for x in I])
    g = [greedy(x, 10, 0)['value'] for x in I]
    per = []
    for j in range(2):
        vals = [R[k * 2 + j][0] for k in range(len(pop))]
        ok = [v for v in vals if v is not None]
        per.append(dict(greedy=g[j], distinct=len(set(ok)), fails=len(vals) - len(ok), best=max(ok) if ok else None, worst=min(ok) if ok else None, med=st.median(ok) if ok else None))
    res[json.dumps(c)] = per; print(c, per, flush=True)
json.dump(res, open('eco/hardness_scan.json', 'w'), indent=1)
