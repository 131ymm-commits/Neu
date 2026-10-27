# PRECOND-01: обвязка основного опыта (вариант A, совет 37) — по образцу THINK-01 harness_think.py. Симулятор, промпт исполнителя,
# схемы и перестановка кандидатов — SELECT-01 без изменений; предусловия собирает prompts_precond.compose.
#   python3 harness_precond.py salt <этап>            — секретная соль этапа (open | val), один раз; печатает sha256 соли
#   python3 harness_precond.py tasks <этап>           — tasks/<задача>.json по seeds_<этап>.json
#   python3 harness_precond.py exec_jobs <этап>       — run/<этап>_exec_jobs.jsonl: исполнитель строит пул k = 8
#   python3 harness_precond.py collect_exec <этап>    — pools/<задача>.json + run/<этап>_exec_pools.sha256 (правда НЕ считается)
#   python3 harness_precond.py eval_jobs open         — run/open_eval_medium_jobs.jsonl (64 сочетания C00–C63 + M0 «всё выключено»)
#                                                       и run/open_eval_high_jobs.jsonl (H0 «всё выключено», H1 «всё включено»)
#   python3 harness_precond.py eval_jobs val          — run/val_eval_medium_jobs.jsonl: OBS, MODEL, ANCHOR × 5 голосов по winners.json
#   python3 harness_precond.py collect_eval <этап>    — evals/<этап>.jsonl из run/<этап>_eval_{medium,high}_out.jsonl
#   python3 harness_precond.py truth <этап>           — правда в секрет этапа; ТОЛЬКО после пуша выборов этапа и события пуша
# Соль этапа — по ключу (open → /root/precond_secret_open, val → /root/precond_secret_val); другой PRECOND_SECRET для этих этапов
# не принимается (как совет 34, Н8). Для сухого прогона — этап dry и явный PRECOND_SECRET.
import collections, hashlib, json, os, random, secrets, sys
HERE = os.path.dirname(os.path.abspath(__file__)); SEL = os.path.join(HERE, '..', '2026-10-07_SELECT-01')
sys.path.insert(0, SEL); sys.path.insert(0, HERE)
import sim, prompts as P, prompts_precond as PP  # noqa: E402
D = os.environ.get('PRECOND_ROOT', HERE)
SECRETS = dict(open='/root/precond_secret_open', val='/root/precond_secret_val')
CELLS = {f'C{i:02d}': row for i, row in enumerate(PP.design(64))}      # номер сочетания = строка design(64); ничьи — меньший номер
EXTRA = dict(M0=([], 'medium'), H0=([], 'high'), H1=(list(PP.F), 'high'))   # совет 37: опорные клетки потолка, в факторный анализ не входят
ANCHOR = ['REFUSE', 'ROLE', 'PROCEDURE']                                 # D_N SELECT-01 байт в байт (= C-клетка плана)
VOTES_VAL = 5

def sec_for(stage):
    env = os.environ.get('PRECOND_SECRET')
    if stage in SECRETS:
        assert env in (None, SECRETS[stage]), f'PRECOND_SECRET={env} не совпадает с этапом {stage}'
        return SECRETS[stage]
    assert env, f'для этапа {stage} нужен явный PRECOND_SECRET (сухой прогон)'
    return env

def salt(sec): return open(f'{sec}/salt.txt').read().strip()
def tids(stage): return [f'WH_{s}' for s in json.load(open(f'{D}/seeds_{stage}.json'))['WH']]
def task(tid): return json.load(open(f'{D}/tasks/{tid}.json'))
def pool(tid): return json.load(open(f'{D}/pools/{tid}.json'))

def perm(tid, k=8):
    p = list(range(k)); random.Random(int(hashlib.sha256(f'{task(tid)["seed"]}|perm'.encode()).hexdigest()[:16], 16)).shuffle(p); return p

def prompt_for(on, tid):
    tk = task(tid); pl = pool(tid); shown = [pl[j] for j in perm(tid)]
    return PP.compose(set(on), sim.RULES[tk['type']](tk), shown)

def write_jobs(name, jobs):
    os.makedirs(f'{D}/run', exist_ok=True); p = f'{D}/run/{name}_jobs.jsonl'
    with open(p, 'w') as fh:
        for j in jobs: fh.write(json.dumps(j, ensure_ascii=False) + '\n')
    # совет 37: sha256 каждого промпта — по id задания (журнал драйвера пишет id), коммитится до первого вызова вместе с заданиями
    json.dump({j['id']: hashlib.sha256(j['prompt'].encode()).hexdigest() for j in jobs}, open(f'{D}/run/{name}_prompts.sha256', 'w'), indent=0)
    print(p, len(jobs), 'голов')

ATT = collections.Counter()
def results(name):
    # как THINK-01 (совет 34, Н5): по id берётся первая несбойная запись; если все сбойные — первая сбойная
    p = f'{D}/run/{name}_out.jsonl'; out = {}
    if not os.path.exists(p): return out
    for r in map(json.loads, open(p)):
        ATT[r['id'].split('|')[1] if r['id'].count('|') == 2 else 'exec'] += 1
        if r['id'] not in out or (out[r['id']].get('error') and not r.get('error')): out[r['id']] = r
    return out

def winners():
    return json.load(open(f'{D}/winners.json'))

if __name__ == '__main__':
    cmd, stage = sys.argv[1], sys.argv[2]
    if cmd == 'salt':
        sec = sec_for(stage); os.makedirs(sec, exist_ok=True); p = f'{sec}/salt.txt'
        if not os.path.exists(p): open(p, 'w').write(secrets.token_hex(32))
        print(sec, 'sha256(salt) =', hashlib.sha256(salt(sec).encode()).hexdigest())
    elif cmd == 'tasks':
        os.makedirs(f'{D}/tasks', exist_ok=True)
        for t in tids(stage):
            typ, s = t.split('_'); json.dump(sim.GEN[typ](int(s)), open(f'{D}/tasks/{t}.json', 'w'))
        print('задач', len(tids(stage)))
    elif cmd == 'exec_jobs':
        write_jobs(f'{stage}_exec', [dict(id=f'{t}|exec', prompt=P.EXEC.format(rules=sim.RULES[task(t)['type']](task(t))), schema=P.EXEC_SCHEMA)
                                     for t in tids(stage)])
    elif cmd == 'collect_exec':
        os.makedirs(f'{D}/pools', exist_ok=True); man = {}
        for lab, r in results(f'{stage}_exec').items():
            t = lab.split('|')[0]; c = (r.get('result') or {}).get('candidates')
            if not c or len(c) != 8: print('нет пула:', t, r.get('error')); continue
            s = json.dumps(c, ensure_ascii=False); open(f'{D}/pools/{t}.json', 'w').write(s); man[t] = hashlib.sha256(s.encode()).hexdigest()
        json.dump(man, open(f'{D}/run/{stage}_exec_pools.sha256', 'w'), indent=0); print('пулов:', len(man))
    elif cmd == 'eval_jobs':
        jobs = dict(medium=[], high=[])
        arms = ({c: (on, 'medium', 1) for c, on in CELLS.items()} | {c: (on, eff, 1) for c, (on, eff) in EXTRA.items()} if stage in ('open', 'dry')
                else {a: (on, 'medium', VOTES_VAL) for a, on in winners()['arms'].items()})
        for t in tids(stage):
            if not os.path.exists(f'{D}/pools/{t}.json'): print('нет пула — задача исключена до оценщиков:', t); continue
            for a, (on, eff, n) in arms.items():
                text, schema = prompt_for(on, t)
                jobs[eff] += [dict(id=f'{t}|{a}|{i}', prompt=text, schema=schema) for i in range(n)]
        for eff, js in jobs.items():
            if js: write_jobs(f'{stage}_eval_{eff}', js)
    elif cmd == 'collect_eval':
        os.makedirs(f'{D}/evals', exist_ok=True); n = 0
        with open(f'{D}/evals/{stage}.jsonl', 'w') as fh:
            for eff in ('medium', 'high'):
                for lab, r in results(f'{stage}_eval_{eff}').items():
                    t, a, i = lab.split('|'); pm = perm(t); res = r.get('result') or {}; c = res.get('choice')
                    ch = None if r.get('error') else (pm[c] if isinstance(c, int) and 0 <= c < len(pm) else c)   # −1 (отказ) и мусор — как есть
                    e = dict(task=t, arm=a, i=int(i), choice=ch, shown_choice=c, error=r.get('error'), inp=r.get('inp', 0), out=r.get('out', 0),
                             models=r.get('models'), retried=r.get('retried', False), effort=eff)
                    if 'p_best' in res: e['p_best'] = res['p_best']
                    fh.write(json.dumps(e, ensure_ascii=False) + '\n'); n += 1
        print(n, 'выборов; попыток по рукам (первые 12):', dict(list(ATT.items())[:12]))
    elif cmd == 'truth':
        sec = sec_for(stage); os.makedirs(f'{sec}/truth', exist_ok=True); slt = salt(sec); n = 0
        for t in tids(stage):
            if os.path.exists(f'{D}/pools/{t}.json'):
                json.dump([sim.truth(task(t), c['plan'], slt) for c in pool(t)], open(f'{sec}/truth/{t}.json', 'w')); n += 1
        print('правда посчитана для', n, 'задач')
