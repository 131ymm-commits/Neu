# SELECT-01: обвязка (редакция 2 — после трёх линз; первая редакция — harness_v1.py, ею сделан пилот 1). Головы — только через run_sealed.py.
#   python3 harness.py salt                                  — создать секретную соль (один раз), напечатать её SHA-256
#   python3 harness.py tasks <seeds.json> <ключ>             — задачи по списку сидов
#   python3 harness.py exec_jobs <stage> <seeds.json> <ключ> — run/<stage>_jobs.jsonl: исполнитель строит пул k = 8 по каждой задаче
#   python3 harness.py collect_exec <stage>                  — pools/<task>.json + run/<stage>_pools.sha256 (правда НЕ считается)
#   python3 harness.py eval_jobs <stage> <рука:N,...> <seeds.json> <ключ> — run/<stage>_jobs.jsonl: оценщики; кандидаты в порядке perm(task)
#   python3 harness.py collect_eval <stage>                  — evals/<stage>.jsonl: выбор (в номерах пула, обратно через perm) + токены
#   python3 harness.py truth <seeds.json> <ключ>             — правда кандидатов в секрет; ТОЛЬКО после collect_eval всех рук (линза 1, п. 2)
# Порядок кандидатов у оценщиков — одна перестановка на задачу по sha256(сид|perm), общая для всех рук (линза 1, п. 3).
import hashlib, json, os, random, secrets, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim, prompts
D = os.environ.get('SELECT_ROOT', os.path.dirname(os.path.abspath(__file__))); SEC = os.environ.get('SELECT_SECRET', '/root/select_secret')

def salt():
    return open(f'{SEC}/salt.txt').read().strip()

def tids(seeds_file, key):
    return [f'{key}_{s}' for s in json.load(open(f'{D}/{seeds_file}'))[key]]

def task(tid):
    return json.load(open(f'{D}/tasks/{tid}.json'))

def perm(tid, k=8):
    p = list(range(k)); random.Random(int(hashlib.sha256(f'{task(tid)["seed"]}|perm'.encode()).hexdigest()[:16], 16)).shuffle(p); return p

def write_jobs(stage, jobs):
    os.makedirs(f'{D}/run', exist_ok=True); p = f'{D}/run/{stage}_jobs.jsonl'
    with open(p, 'w') as fh:
        for j in jobs: fh.write(json.dumps(j, ensure_ascii=False) + '\n')
    print(p, len(jobs), 'голов')

def results(stage):
    return {r['id']: r for r in map(json.loads, open(f'{D}/run/{stage}_out.jsonl'))}   # последняя запись по id

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'salt':
        os.makedirs(SEC, exist_ok=True); p = f'{SEC}/salt.txt'
        if not os.path.exists(p): open(p, 'w').write(secrets.token_hex(32))
        print('sha256(salt) =', hashlib.sha256(salt().encode()).hexdigest())
    elif cmd == 'tasks':
        os.makedirs(f'{D}/tasks', exist_ok=True)
        for t in tids(sys.argv[2], sys.argv[3]):
            typ, s = t.split('_'); json.dump(sim.GEN[typ](int(s)), open(f'{D}/tasks/{t}.json', 'w'))
        print('задач', len(tids(sys.argv[2], sys.argv[3])))
    elif cmd == 'exec_jobs':
        write_jobs(sys.argv[2], [dict(id=f'{t}|exec', prompt=prompts.EXEC.format(rules=sim.RULES[task(t)['type']](task(t))), schema=prompts.EXEC_SCHEMA)
                                 for t in tids(sys.argv[3], sys.argv[4])])
    elif cmd == 'collect_exec':
        stage = sys.argv[2]; os.makedirs(f'{D}/pools', exist_ok=True); man = {}
        for lab, r in results(stage).items():
            t = lab.split('|')[0]; c = (r.get('result') or {}).get('candidates')
            if not c or len(c) != 8: print('нет пула:', t, r.get('error')); continue
            s = json.dumps(c, ensure_ascii=False); open(f'{D}/pools/{t}.json', 'w').write(s); man[t] = hashlib.sha256(s.encode()).hexdigest()
        json.dump(man, open(f'{D}/run/{stage}_pools.sha256', 'w'), indent=0); print('пулов:', len(man))
    elif cmd == 'eval_jobs':
        stage, spec = sys.argv[2], dict(x.split(':') for x in sys.argv[3].split(',')); jobs = []
        for t in tids(sys.argv[4], sys.argv[5]):
            tk = task(t); pool = json.load(open(f'{D}/pools/{t}.json')); pm = perm(t); shown = [pool[j] for j in pm]; rules = sim.RULES[tk['type']](tk)
            for a, n in spec.items():
                for i in range(int(n)):
                    jobs.append(dict(id=f'{t}|{a}|{i}', prompt=prompts.eval_prompt(a, rules, shown), schema=prompts.EVAL_SCHEMA))
        write_jobs(stage, jobs)
    elif cmd == 'collect_eval':
        stage = sys.argv[2]; os.makedirs(f'{D}/evals', exist_ok=True); n = 0
        with open(f'{D}/evals/{stage}.jsonl', 'w') as fh:
            for lab, r in results(stage).items():
                t, a, i = lab.split('|'); pm = perm(t); c = (r.get('result') or {}).get('choice')
                ch = None if r.get('error') else (pm[c] if isinstance(c, int) and 0 <= c < len(pm) else c)   # −1 (отказ) и мусор — как есть
                fh.write(json.dumps(dict(task=t, arm=a, i=int(i), choice=ch, shown_choice=c, error=r.get('error'), inp=r.get('inp', 0), out=r.get('out', 0),
                                         models=r.get('models'), retried=r.get('retried', False)), ensure_ascii=False) + '\n'); n += 1
        print(n, 'выборов')
    elif cmd == 'truth':
        os.makedirs(f'{SEC}/truth', exist_ok=True); slt = salt(); n = 0
        for t in tids(sys.argv[2], sys.argv[3]):
            p = f'{D}/pools/{t}.json'
            if os.path.exists(p):
                json.dump([sim.truth(task(t), c['plan'], slt) for c in json.load(open(p))], open(f'{SEC}/truth/{t}.json', 'w')); n += 1
        print('правда посчитана для', n, 'задач')
