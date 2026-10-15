# THINK-01: обвязка — по образцу SELECT-01 (harness.py, редакция 2); симулятор, промпт исполнителя и схемы — из SELECT-01 без изменений.
#   python3 harness_think.py salt                                   — секретная соль (один раз), печатает её SHA-256
#   python3 harness_think.py tasks <seeds.json> <ключ>              — задачи по списку сидов
#   python3 harness_think.py exec_jobs <stage> <seeds.json> <ключ>  — run/<stage>_jobs.jsonl: исполнитель строит пул k = 8
#   python3 harness_think.py collect_exec <stage>                   — pools/<task>.json + run/<stage>_pools.sha256 (правда НЕ считается)
#   python3 harness_think.py eval_jobs <stage> <seeds.json> <ключ>  — run/<stage>_{medium,high}_jobs.jsonl: руки prompts_think.SPEC;
#       effort задаётся конфигом прогона (run/think01_medium.json, run/think01_high.json), поэтому задания разделены по effort
#   python3 harness_think.py collect_eval <stage>                   — evals/<stage>.jsonl из run/<stage>_{medium,high}_out.jsonl
#   python3 harness_think.py truth <seeds.json> <ключ>              — правда кандидатов в секрет; ТОЛЬКО после коммита выборов
# Порядок кандидатов у оценщиков — одна перестановка на задачу по sha256(сид|perm), общая для всех рук (как в SELECT-01).
import hashlib, json, os, random, secrets, sys
HERE = os.path.dirname(os.path.abspath(__file__)); SEL = os.path.join(HERE, '..', '2026-10-07_SELECT-01')
sys.path.insert(0, SEL); sys.path.insert(0, HERE)
import sim, prompts as P, prompts_think as PT  # noqa: E402
D = os.environ.get('THINK_ROOT', HERE); SEC = os.environ.get('THINK_SECRET', '/root/think_secret')

def salt():
    return open(f'{SEC}/salt.txt').read().strip()

def tids(seeds_file, key):
    return [f'{key}_{s}' for s in json.load(open(f'{D}/{seeds_file}'))[key]]

def task(tid):
    return json.load(open(f'{D}/tasks/{tid}.json'))

def perm(tid, k=8):
    p = list(range(k)); random.Random(int(hashlib.sha256(f'{task(tid)["seed"]}|perm'.encode()).hexdigest()[:16], 16)).shuffle(p); return p

def write_jobs(name, jobs):
    os.makedirs(f'{D}/run', exist_ok=True); p = f'{D}/run/{name}_jobs.jsonl'
    with open(p, 'w') as fh:
        for j in jobs: fh.write(json.dumps(j, ensure_ascii=False) + '\n')
    print(p, len(jobs), 'голов')

def results(name):
    p = f'{D}/run/{name}_out.jsonl'
    return {r['id']: r for r in map(json.loads, open(p))} if os.path.exists(p) else {}   # последняя запись по id

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
        write_jobs(sys.argv[2], [dict(id=f'{t}|exec', prompt=P.EXEC.format(rules=sim.RULES[task(t)['type']](task(t))), schema=P.EXEC_SCHEMA)
                                 for t in tids(sys.argv[3], sys.argv[4])])
    elif cmd == 'collect_exec':
        stage = sys.argv[2]; os.makedirs(f'{D}/pools', exist_ok=True); man = {}
        for lab, r in results(stage).items():
            t = lab.split('|')[0]; c = (r.get('result') or {}).get('candidates')
            if not c or len(c) != 8: print('нет пула:', t, r.get('error')); continue
            s = json.dumps(c, ensure_ascii=False); open(f'{D}/pools/{t}.json', 'w').write(s); man[t] = hashlib.sha256(s.encode()).hexdigest()
        json.dump(man, open(f'{D}/run/{stage}_pools.sha256', 'w'), indent=0); print('пулов:', len(man))
    elif cmd == 'eval_jobs':
        stage = sys.argv[2]; jobs = dict(medium=[], high=[])
        for t in tids(sys.argv[3], sys.argv[4]):
            if not os.path.exists(f'{D}/pools/{t}.json'): print('нет пула — задача исключена до оценщиков:', t); continue
            tk = task(t); pool = json.load(open(f'{D}/pools/{t}.json')); shown = [pool[j] for j in perm(t)]; rules = sim.RULES[tk['type']](tk)
            for a, n in PT.SPEC.items():
                tpl, eff, schema = PT.ARMS[a]
                jobs[eff] += [dict(id=f'{t}|{a}|{i}', prompt=PT.eval_prompt(a, rules, shown), schema=schema) for i in range(n)]
        for eff, js in jobs.items(): write_jobs(f'{stage}_{eff}', js)
    elif cmd == 'collect_eval':
        stage = sys.argv[2]; os.makedirs(f'{D}/evals', exist_ok=True); n = 0
        with open(f'{D}/evals/{stage}.jsonl', 'w') as fh:
            for eff in ('medium', 'high'):
                for lab, r in results(f'{stage}_{eff}').items():
                    t, a, i = lab.split('|'); pm = perm(t); res = r.get('result') or {}; c = res.get('choice')
                    ch = None if r.get('error') else (pm[c] if isinstance(c, int) and 0 <= c < len(pm) else c)   # −1 (отказ) и мусор — как есть
                    e = dict(task=t, arm=a, i=int(i), choice=ch, shown_choice=c, error=r.get('error'), inp=r.get('inp', 0), out=r.get('out', 0),
                             models=r.get('models'), retried=r.get('retried', False), effort=eff)
                    if 'p_best' in res: e['p_best'] = res['p_best']
                    fh.write(json.dumps(e, ensure_ascii=False) + '\n'); n += 1
        print(n, 'выборов')
    elif cmd == 'truth':
        os.makedirs(f'{SEC}/truth', exist_ok=True); slt = salt(); n = 0
        for t in tids(sys.argv[2], sys.argv[3]):
            p = f'{D}/pools/{t}.json'
            if os.path.exists(p):
                json.dump([sim.truth(task(t), c['plan'], slt) for c in json.load(open(p))], open(f'{SEC}/truth/{t}.json', 'w')); n += 1
        print('правда посчитана для', n, 'задач')
