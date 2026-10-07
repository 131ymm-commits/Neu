# SELECT-01: сухой прогон цепочки на заглушках (без голов): задачи → пул из эвристик с шумными заявками → «выборы» → анализ.
#   python3 dryrun.py <папка-песочница>
import json, os, random, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__)); box = os.path.abspath(sys.argv[1]); os.makedirs(box, exist_ok=True)
env = dict(os.environ, SELECT_ROOT=box, SELECT_SECRET=box + '/secret'); os.makedirs(box + '/secret', exist_ok=True)
open(box + '/secret/salt.txt', 'w').write('dryrun-salt')
sys.path.insert(0, here); import sim
r = random.Random(0); os.makedirs(box + '/tasks', exist_ok=True); os.makedirs(box + '/pools', exist_ok=True); os.makedirs(box + '/secret/truth', exist_ok=True)
ev = open(box + '/evals.jsonl', 'w')
for typ in ('WH', 'SC'):
    kinds = ['cover', 'batch'] if typ == 'WH' else ['edd', 'wspt', 'fam', 'rand']
    H = sim.heur_wh if typ == 'WH' else sim.heur_sc
    for s in range(1, 13):
        t = sim.GEN[typ](s); tid = f'{typ}_{s}'; json.dump(t, open(f'{box}/tasks/{tid}.json', 'w'))
        pool = []
        for j in range(8):
            p = H(t, kinds[j % len(kinds)], r); tv = sim.truth(t, p, 'dryrun-salt', 50)
            pool.append(dict(plan=p, claim=round(tv * r.uniform(.8, 1.4) + 300 * r.gauss(0, 1)), doubt=round(r.random(), 2), note='заглушка'))
        json.dump(pool, open(f'{box}/pools/{tid}.json', 'w'))
        json.dump([sim.truth(t, c['plan'], 'dryrun-salt') for c in pool], open(f'{box}/secret/truth/{tid}.json', 'w'))
        for arm, n in (('A', 1), ('B_blind', 5), ('C_N', 5), ('D_N', 5), ('C', 1), ('D', 1), ('B_zayavka', 5)):
            for i in range(n):
                ch = r.choice([-1] + list(range(8))) if arm.startswith('D') else r.randrange(8)
                ev.write(json.dumps(dict(task=tid, arm=arm, i=i, choice=ch, inp=1000, out=50)) + '\n')
ev.close()
for typ in ('WH', 'SC'):
    subprocess.run([sys.executable, here + '/analyze.py', typ, box + '/evals.jsonl', '--out', f'{box}/an_{typ}.json'], env=env, check=True)
