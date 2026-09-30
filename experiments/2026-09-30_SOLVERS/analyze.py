# Турнир решателей: анализ пилота (описательный) — g = (ref − x)/(ref − greedy), исключение экземпляров по признакам, не зависящим от рук.
import json, os, sys, statistics as st, random
HERE = os.path.dirname(os.path.abspath(__file__)); RUN = os.path.join(HERE, os.environ.get('SOLV_RUN', 'run'))
EPS = 20
refs = json.load(open(sys.argv[1] if len(sys.argv) > 1 else '/root/solvers_secret/refs.json'))
fin = json.load(open(os.path.join(RUN, 'final.json'))); test = json.load(open(os.path.join(HERE, 'inst', 'test.json')))
keep = [i for i, inst in enumerate(test) if refs[f"test{inst['seed']}"]['ref'] - refs[f"test{inst['seed']}"]['greedy'] >= EPS]
def g(i, x):
    r = refs[f"test{test[i]['seed']}"]; return (r['ref'] - x) / (r['ref'] - r['greedy'])
arms = sorted({k[:-1] for k in fin}); reps = sorted({int(k[-1]) for k in fin})
G = {a: {rep: [g(i, fin[f'{a}{rep}']['values']['0'][i]) for i in keep] for rep in reps} for a in arms}
res = dict(eps=EPS, n_test=len(test), kept=len(keep), excluded=[test[i]['seed'] for i in range(len(test)) if i not in keep])
res['median_g'] = {a: {rep: st.median(G[a][rep]) for rep in reps} for a in arms}
res['median_g_pooled'] = {a: st.median(sum(G[a].values(), [])) for a in arms}
res['beat_ref_share'] = {a: sum(x < 0 for x in sum(G[a].values(), [])) / (len(keep) * len(reps)) for a in arms}
# шум семени: разброс g по семенам 0,1,2 у одной программы (среднее по экземплярам стандартного отклонения)
res['seed_noise'] = {a: st.mean(st.mean(st.pstdev([g(i, fin[f'{a}{rep}']['values'][s][i]) for s in ('0', '1', '2')]) for i in keep) for rep in reps) for a in arms}
# парные разности по (экземпляр, повтор): обмен − изоляция, обмен − самопродолжение; бутстреп медианы разности
def paired(a, b):
    d = [x - y for rep in reps for x, y in zip(G[a][rep], G[b][rep])]
    rng = random.Random(0); bs = sorted(st.median([rng.choice(d) for _ in d]) for _ in range(2000))
    return dict(median_diff=st.median(d), ci95=[bs[50], bs[1949]], n=len(d), sd=st.pstdev(d))
res['ex_minus_iso'] = paired('ex', 'iso'); res['ex_minus_self'] = paired('ex', 'self'); res['tx_minus_self'] = paired('tx', 'self'); res['self_minus_iso'] = paired('self', 'iso')
json.dump(res, open(os.path.join(RUN, 'analysis.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
