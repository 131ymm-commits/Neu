# PRECOND-01: сухой прогон основного опыта (до PREREG; совет 37 — «тест на синтетике с известными действиями», «прогон на фиктивной правде»).
#   python3 dryrun_precond_main.py <пустой каталог>
# 1) Синтетика: регреты 9 задач × 64 сочетания с известными действиями (REFUSE −0,3, ROLE −0,2, прочие 0; sd шума 0,575) —
#    оценки, Freedman–Lane, Холм, t-ДИ. 2) Вся цепочка обвязки и анализа на заглушках: задачи и пулы SELECT-01 (WH_8001–8009),
#    соль сухого прогона, случайные выборы вместо голов (часть — отказы и сбои), правда, анализ открытия и проверки победителя.
import json, os, random, shutil, subprocess, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); SEL = os.path.join(HERE, '..', '2026-10-07_SELECT-01')
root = os.path.abspath(sys.argv[1]); assert os.path.isdir(root) and not os.listdir(root), 'нужен пустой каталог'
sys.path.insert(0, HERE)
import analyze_precond as A, prompts_precond as PP  # noqa: E402
A.B = 2000; ok = True
def check(cond, msg):
    global ok; ok &= bool(cond); print(('ок  ' if cond else 'СБОЙ') + ' ' + msg)

# ---------- 1. синтетика ----------
rng = np.random.default_rng(1); true = dict(REFUSE=-0.3, ROLE=-0.2); reps, est, rej = 60, {f: [] for f in PP.F}, {f: 0 for f in PP.F}
for _ in range(reps):
    Yraw = rng.normal(0, 0.3, (9, 1)) + 0.5 + rng.normal(0, 0.575, (9, 64))
    for f, e in true.items(): Yraw += (e / 2) * A.X[:, PP.F.index(f)]
    Y = Yraw - Yraw.mean(axis=1, keepdims=True)
    for j, f in enumerate(PP.F):
        b, p = A.fl_p(Y, A.X[:, j], np.delete(A.X, j, axis=1), rng); est[f].append(2 * b); rej[f] += p < 0.05
check(abs(np.mean(est['REFUSE']) + 0.3) < 0.03 and abs(np.mean(est['ROLE']) + 0.2) < 0.03, f'оценки действий несмещены: REFUSE {np.mean(est["REFUSE"]):.3f}, ROLE {np.mean(est["ROLE"]):.3f}')
nulls = [f for f in PP.F if f not in true]; fpr = sum(rej[f] for f in nulls) / (reps * len(nulls))
check(0.0 <= fpr <= 0.1, f'ложные срабатывания Freedman–Lane при α 0,05: {fpr:.3f} (ожидание около 0,05)')
check(rej['REFUSE'] / reps > 0.8, f'мощность для REFUSE −0,3 на 9 задачах: {rej["REFUSE"] / reps:.2f}')
check(A.holm([('a', 0.001), ('b', 0.02), ('c', 0.04)]) == dict(a=True, b=True, c=True) and A.holm([('a', 0.03), ('b', 0.04)]) == dict(a=False, b=False), 'Холм')
cov = 0
for _ in range(400):
    v = list(rng.normal(0.1, 0.5, 9)); c = A.t_ci(v)['ci95']; cov += c[0] <= 0.1 <= c[1]
check(0.92 <= cov / 400 <= 0.98, f'покрытие t-ДИ (df 8): {cov / 400:.3f}')

# ---------- 2. вся цепочка на заглушках ----------
for d in ('tasks', 'pools'): os.makedirs(f'{root}/{d}')
dry = [f'WH_{s}' for s in range(8001, 8010)]
for t in dry:
    shutil.copy(f'{SEL}/tasks/{t}.json', f'{root}/tasks/'); shutil.copy(f'{SEL}/pools/{t}.json', f'{root}/pools/')
json.dump({'WH': list(range(8001, 8010))}, open(f'{root}/seeds_dry.json', 'w')); json.dump({'WH': list(range(8001, 8010))}, open(f'{root}/seeds_dryval.json', 'w'))
env = dict(os.environ, PRECOND_ROOT=root, PRECOND_SECRET=f'{root}/secret')
H = lambda *a: subprocess.run([sys.executable, f'{HERE}/harness_precond.py', *a], env=env, check=True, capture_output=True, text=True).stdout
def fake(name, seed):
    rr = random.Random(seed); n = 0
    with open(f'{root}/run/{name}_out.jsonl', 'w') as fh:
        for j in map(json.loads, open(f'{root}/run/{name}_jobs.jsonl')):
            u = rr.random(); res = None if u < 0.02 else dict(choice=-1 if u < 0.06 else rr.randrange(8))
            if res is not None and 'p_best' in j['schema']['properties']: res['p_best'] = round(rr.random(), 2)
            fh.write(json.dumps(dict(id=j['id'], result=res, error='сбой' if res is None else None, out=rr.randrange(2000, 9000), inp=6000,
                                     models={'stub': 1}), ensure_ascii=False) + '\n'); n += 1
    return n
H('salt', 'dry'); H('eval_jobs', 'dry')
nm, nh = fake('dry_eval_medium', 1), fake('dry_eval_high', 2)
check(nm == 9 * 65 and nh == 9 * 2, f'задания открытия: medium {nm} (= 9 × 65), high {nh} (= 9 × 2)')
jobs = [json.loads(l) for l in open(f'{root}/run/dry_eval_medium_jobs.jsonl')]
ids = {j['id'].split('|')[1] for j in jobs}; check(ids == set(A.CELLS) | {'M0'}, 'клетки medium: C00–C63 и M0')
man = json.load(open(f'{root}/run/dry_eval_medium_prompts.sha256')); import hashlib
check(len(man) == nm and all(man[j['id']] == hashlib.sha256(j['prompt'].encode()).hexdigest() for j in jobs), 'манифест sha256 промптов по id заданий')
anchor = next(j for j in jobs if j['id'] == f'WH_8001|{A.ANCH}|0')['prompt']
sys.path.insert(0, os.path.join(HERE, '..', '2026-10-15_THINK-01')); import prompts_think as PT, harness_precond as HP  # noqa: E402
HP.D = root; tk = HP.task('WH_8001'); shown = [HP.pool('WH_8001')[i] for i in HP.perm('WH_8001')]
check(anchor == PT.eval_prompt('D_N', __import__('sim').RULES[tk['type']](tk), shown), 'промпт опоры (C44) байт в байт равен D_N SELECT-01 / THINK-01')
H('collect_eval', 'dry'); H('truth', 'dry')
r = subprocess.run([sys.executable, f'{HERE}/analyze_precond.py', 'open', f'{root}/evals/dry.jsonl', '--key', 'dry', '--out', f'{root}/open_an.json'],
                   env=env, capture_output=True, text=True)
check(r.returncode == 0, 'анализ открытия на заглушках отработал' + ('' if r.returncode == 0 else ': ' + r.stderr[-400:]))
o = json.load(open(f'{root}/open_an.json')); w = json.load(open(f'{root}/winners.json'))
check(set(o['main_effects']) == set(PP.F) and 'p_fl' in o['main_effects']['REFUSE'] and o['ceiling']['outcome'], 'в выводе есть главные действия, p и потолок')
check(o['Q1']['p'] > 0.01, f'вопрос 1 на случайных выборах не срабатывает: p = {o["Q1"]["p"]}')
check(set(w['arms']) | set(w['aliases']) == {'OBS', 'MODEL', 'ANCHOR'}, f'победители: {w}')
H('eval_jobs', 'dryval'); nv = fake('dryval_eval_medium', 3)
check(nv == 9 * len(w['arms']) * 5, f'задания проверки: {nv} (= 9 × {len(w["arms"])} рук × 5)')
H('collect_eval', 'dryval'); H('truth', 'dryval')
r = subprocess.run([sys.executable, f'{HERE}/analyze_precond.py', 'val', f'{root}/evals/dryval.jsonl', '--key', 'dryval', '--out', f'{root}/val_an.json',
                    '--open-an', f'{root}/open_an.json'], env=env, capture_output=True, text=True)
check(r.returncode == 0, 'анализ проверки победителя на заглушках отработал' + ('' if r.returncode == 0 else ': ' + r.stderr[-400:]))
v = json.load(open(f'{root}/val_an.json')); check('primary' in v and 'shrinkage' in v, f'первичный исход проверки: {v["primary"].get("outcome")}')
print('СУХОЙ ПРОГОН ПРОЙДЕН' if ok else 'СУХОЙ ПРОГОН НЕ ПРОЙДЕН'); sys.exit(0 if ok else 1)
