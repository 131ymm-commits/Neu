# THINK-01: сухой прогон всей цепочки на заглушках (ворота CLAUDE.md: «сухой прогон до регистрации»). Головы не вызываются.
#   python3 dryrun_think.py   — во временном каталоге: задачи (настоящий sim.GEN), фальшивые пулы и правда, eval_jobs,
#   фальшивые выгрузки в формате run_sealed2 export, collect_eval, analyze_think; два сценария — с заложенным эффектом и без.
# Проверки: число заданий по effort; промпты B_blind, C_N, D_N совпадают с SELECT-01 байт в байт; обратная перестановка в
# collect_eval (доля попаданий в лучшего по правде у H совпадает с заложенной); эффект находится; при нуле не засчитывается.
import json, os, random, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); SEL = os.path.join(HERE, '..', '2026-10-07_SELECT-01')
sys.path.insert(0, SEL); sys.path.insert(0, HERE)
import sim, prompts as P, prompts_think as PT  # noqa: E402
N = 40; SEEDS = list(range(9901, 9901 + N)); ok_all = True

def check(cond, msg):
    global ok_all
    print(('ОК  ' if cond else 'ОШИБКА  ') + msg); ok_all &= bool(cond)

def scenario(name, p_hit):
    root = tempfile.mkdtemp(prefix=f'think_dry_{name}_'); sec = os.path.join(root, 'secret'); os.makedirs(f'{sec}/truth'); os.makedirs(f'{root}/pools')
    env = dict(os.environ, THINK_ROOT=root, THINK_SECRET=sec)
    json.dump({'WH': SEEDS}, open(f'{root}/seeds.json', 'w'))
    H = lambda *a: subprocess.run([sys.executable, f'{HERE}/harness_think.py', *a], env=env, capture_output=True, text=True, check=True).stdout
    H('tasks', 'seeds.json', 'WH'); rng = random.Random(name)
    for s in SEEDS:
        t = f'WH_{s}'
        pool = [dict(plan={'id': j}, claim=rng.uniform(0, 1000), doubt=rng.uniform(0, 1), note='заглушка') for j in range(8)]
        json.dump(pool, open(f'{root}/pools/{t}.json', 'w'), ensure_ascii=False)
        json.dump([rng.uniform(0, 1000) for _ in range(8)], open(f'{sec}/truth/{t}.json', 'w'))
    H('eval_jobs', 'dry', 'seeds.json', 'WH')
    jobs = {eff: [json.loads(l) for l in open(f'{root}/run/dry_{eff}_jobs.jsonl')] for eff in ('medium', 'high')}
    check(len(jobs['medium']) == N * 32 and len(jobs['high']) == N * 4, f'{name}: заданий medium {len(jobs["medium"])}, high {len(jobs["high"])} (ждём {N * 32} и {N * 4})')
    sys.path.insert(0, HERE); os.environ['THINK_ROOT'] = root
    import importlib, harness_think as HT; importlib.reload(HT)
    t0 = f'WH_{SEEDS[0]}'; tk = HT.task(t0); pool = json.load(open(f'{root}/pools/{t0}.json')); shown = [pool[j] for j in HT.perm(t0)]
    rules = sim.RULES['WH'](tk); byid = {j['id']: j['prompt'] for js in jobs.values() for j in js}
    for arm in ('B_blind', 'C_N', 'D_N'):
        check(byid[f'{t0}|{arm}|0'] == P.eval_prompt(arm, rules, shown), f'{name}: промпт {arm} совпадает с SELECT-01')
    check(byid[f'{t0}|H|0'] == P.eval_prompt('C_N', rules, shown), f'{name}: промпт H = промпт C_N из SELECT-01')
    hits = []
    for eff, js in jobs.items():
        with open(f'{root}/run/dry_{eff}_out.jsonl', 'w') as fh:
            for j in js:
                t, arm, i = j['id'].split('|'); tr = json.load(open(f'{sec}/truth/{t}.json')); best = tr.index(max(tr)); pm = HT.perm(t)
                if arm == 'D_N' and rng.random() < 0.1: c = -1
                elif rng.random() < p_hit[arm]: c = pm.index(best)
                else: c = rng.randrange(8)
                if arm == 'H': hits.append(pm[c] == best)
                res = dict(choice=c) | (dict(p_best=0.7) if arm == 'H_c' else {})
                fh.write(json.dumps(dict(id=j['id'], result=res, error=None, inp=7000, out=13000 if eff == 'high' else 3000, models={'stub': 1})) + '\n')
    H('collect_eval', 'dry')
    ev = [json.loads(l) for l in open(f'{root}/evals/dry.jsonl')]
    hit_back = sum(1 for e in ev if e['arm'] == 'H' and e['choice'] == json.load(open(f'{sec}/truth/{e["task"]}.json')).index(max(json.load(open(f'{sec}/truth/{e["task"]}.json'))))) / max(1, sum(e['arm'] == 'H' for e in ev))
    check(abs(hit_back - sum(hits) / len(hits)) < 1e-9, f'{name}: обратная перестановка верна (попаданий H {hit_back:.3f})')
    r = subprocess.run([sys.executable, f'{HERE}/analyze_think.py', f'{root}/evals/dry.jsonl', '--out', f'{root}/an.json'], env=env, capture_output=True, text=True)
    check(r.returncode == 0, f'{name}: analyze_think отработал' + ('' if r.returncode == 0 else ': ' + r.stderr[-500:]))
    an = json.load(open(f'{root}/an.json')) if r.returncode == 0 else None
    shutil.rmtree(root)
    return an

eff = scenario('effect', dict(B_blind=0.25, C_N=0.25, D_N=0.3, U_N=0.25, P_N=0.25, H=0.8, H_c=0.8))
null = scenario('null', {a: 0.3 for a in PT.SPEC})
if eff:
    q = eff['primary']
    check(all(v['counts'] for v in q.values()), 'эффект: обе первичные разности засчитаны: ' + str({k: (v['mean'], round(v['p'], 5), v['budget_ok']) for k, v in q.items()}))
    check('S3_self_assessment' in eff['secondary'] and eff['secondary']['S3_self_assessment']['n'] == N, 'эффект: калибровка H_c посчитана на всех задачах')
if null:
    check(not any(v['counts'] for v in null['primary'].values()), 'ноль: ничего не засчитано: ' + str({k: (v['mean'], round(v['p'], 3)) for k, v in null['primary'].items()}))
print('СУХОЙ ПРОГОН:', 'ПРОЙДЕН' if ok_all else 'ЕСТЬ ОШИБКИ')
sys.exit(0 if ok_all else 1)
