# PRECOND-02: повтор действия REFUSE одним контрастом (совет 39) — обвязка по образцу PRECOND-01 harness_precond.py.
# Руки: ANCHOR = {REFUSE, ROLE, PROCEDURE} (клетка C44 PRECOND-01 = D_N SELECT-01 байт в байт) и NOREF = {ROLE, PROCEDURE}
# (= C_N SELECT-01 байт в байт), по 5 голосов на задачу, effort medium. Симулятор, промпт исполнителя, схемы, перестановка
# кандидатов и сборка промптов — SELECT-01 и PRECOND-01 без изменений (prompts_precond.compose).
#   python3 harness_precond02.py salt <этап>          — секретная соль этапа (pilot | A | B), один раз; печатает sha256 соли
#   python3 harness_precond02.py tasks <этап>         — tasks/<задача>.json по seeds_<этап>.json
#   python3 harness_precond02.py exec_jobs <этап>     — run/<этап>_exec_jobs.jsonl: исполнитель строит пул k = 8
#   python3 harness_precond02.py collect_exec <этап>  — pools/<задача>.json + run/<этап>_exec_pools.sha256 (правда НЕ считается)
#   python3 harness_precond02.py eval_jobs <этап>     — run/<этап>_eval_jobs.jsonl: ANCHOR и NOREF × 5 голосов;
#                                                     для B код требует закоммиченного interim_an.json с решением «продолжить»
#   python3 harness_precond02.py collect_eval <этап>  — evals/<этап>.jsonl из run/<этап>_eval_out.jsonl
#   python3 harness_precond02.py push_event <этап> [--local] — <этап>_push_activity.json: серверное событие GitHub о пуше HEAD
#   python3 harness_precond02.py truth <этап>         — правда в секрет этапа; код сам проверяет порядок (как PRECOND-01, совет 38 К1)
# Соль этапа — по ключу (/root/precond02_secret_<этап>); другой PRECOND02_SECRET для этих этапов не принимается.
# Для сухого прогона — этапы dry, dryB и явный PRECOND02_SECRET.
import datetime, hashlib, json, os, random, secrets, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); EXP = os.path.join(HERE, '..')
SEL, PC1 = os.path.join(EXP, '2026-10-07_SELECT-01'), os.path.join(EXP, '2026-10-21_PRECOND-01')
sys.path.insert(0, SEL); sys.path.insert(0, PC1)
import sim, prompts as P, prompts_precond as PP  # noqa: E402
D = os.environ.get('PRECOND02_ROOT', HERE)
SECRETS = dict(pilot='/root/precond02_secret_pilot', A='/root/precond02_secret_A', B='/root/precond02_secret_B')
ARMS = dict(ANCHOR=['REFUSE', 'ROLE', 'PROCEDURE'], NOREF=['ROLE', 'PROCEDURE'])
VOTES = 5
PREV = dict(B='A', dryB='dry')                 # этап B продолжает этап A: задачи не пересекаются, решение промежуточного анализа — «продолжить»
NEXT = {v: k for k, v in PREV.items()}
TEST = ('A', 'B')                              # этапы теста: перед заданиями B, промежуточным и итоговым анализом код сверяет хеши регистрации

def sec_for(stage):
    env = os.environ.get('PRECOND02_SECRET')
    if stage in SECRETS:
        assert env in (None, SECRETS[stage]), f'PRECOND02_SECRET={env} не совпадает с этапом {stage}'
        return SECRETS[stage]
    assert env, f'для этапа {stage} нужен явный PRECOND02_SECRET (сухой прогон)'
    return f'{env}/{stage}'

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
    json.dump({j['id']: hashlib.sha256(j['prompt'].encode()).hexdigest() for j in jobs}, open(f'{D}/run/{name}_prompts.sha256', 'w'), indent=0)
    print(p, len(jobs), 'голов')

def results(name):
    # как PRECOND-01 и THINK-01 (совет 34, Н5): по id берётся первая несбойная запись; если все сбойные — первая сбойная
    p = f'{D}/run/{name}_out.jsonl'; out = {}
    if not os.path.exists(p): return out
    for r in map(json.loads, open(p)):
        if r['id'] not in out or (out[r['id']].get('error') and not r.get('error')): out[r['id']] = r
    return out

# ---------- порядок «выборы → пуш → событие → правда» и «промежуточное решение → задания B» проверяет код ----------
def git(*a): return subprocess.run(['git', '-C', D, *a], capture_output=True, text=True)
def committed_clean(rel):
    assert git('ls-files', '--error-unmatch', rel).returncode == 0, f'{rel} не закоммичен'
    assert git('diff', '--quiet', 'HEAD', '--', rel).returncode == 0, f'{rel} изменён после коммита'
def sha_file(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
def missing_pools(stage):
    # совет 40, правка 3: задача без пула исключается только явно — по закоммиченному списку collect_exec, не молча
    rel = f'run/{stage}_exec_missing.json'; committed_clean(rel); return set(json.load(open(f'{D}/{rel}')))
def guard_pools(stages):
    # пулы всех задач этапов закоммичены и совпадают с манифестом collect_exec (до правды этапа A — совет 40, правка 3)
    for st_ in stages:
        man_rel = f'run/{st_}_exec_pools.sha256'; committed_clean(man_rel); man = json.load(open(f'{D}/{man_rel}')); miss = missing_pools(st_)
        for t in tids(st_):
            if t in miss: assert t not in man, f'{t}: и в пулах, и в пропусках'; continue
            committed_clean(f'pools/{t}.json'); assert sha_file(f'{D}/pools/{t}.json') == man[t], f'пул {t} не совпадает с манифестом'
def verify_hashes(stage):
    # совет 40, правка 2: код, план, сиды и конфигурация — те же, что при регистрации (prereg_hashes.json закоммичен)
    if stage not in TEST: return
    committed_clean('prereg_hashes.json'); ph = json.load(open(f'{D}/prereg_hashes.json'))
    for f, h in ph['files'].items():
        assert sha_file(os.path.join(HERE, f)) == h, f'{f} изменён после регистрации'
def guard_truth(stage):
    verify_hashes(stage)
    rel = f'evals/{stage}.jsonl'; committed_clean(rel); committed_clean(f'{stage}_push_activity.json'); committed_clean(f'run/{stage}_eval_prompts.sha256')
    if stage in NEXT: guard_pools([stage, NEXT[stage]])         # до правды этапа A — пулы обоих этапов в git
    pa = json.load(open(f'{D}/{stage}_push_activity.json')); after = pa['event']['after']
    assert git('merge-base', '--is-ancestor', after, 'HEAD').returncode == 0, f'коммит события {after[:7]} не предок HEAD'
    pushed = subprocess.run(['git', '-C', D, 'show', f'{after}:./{rel}'], capture_output=True).stdout
    assert hashlib.sha256(pushed).hexdigest() == sha_file(f'{D}/{rel}') == pa['evals_sha256'], 'выборы на диске не совпадают с запушенными'
def guard_b_jobs(stage):
    verify_hashes(stage); prev = PREV[stage]; committed_clean('interim_an.json')
    assert not set(tids(stage)) & set(tids(prev)), 'задачи этапа B пересекаются с задачами этапа A'
    import analyze_precond02 as AN
    re_ = AN.interim(f'{D}/evals/{prev}.jsonl', prev)
    assert re_ == json.load(open(f'{D}/interim_an.json')), 'interim_an.json не совпадает с пересчётом'
    assert re_['decision'] == 'продолжить', f'промежуточное решение — {re_["decision"]}: этап B не ставится'

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
        miss = sorted(set(tids(stage)) - set(man))
        json.dump(man, open(f'{D}/run/{stage}_exec_pools.sha256', 'w'), indent=0); json.dump(miss, open(f'{D}/run/{stage}_exec_missing.json', 'w'))
        print('пулов:', len(man), '| без пула:', miss)
    elif cmd == 'push_event':
        head = git('rev-parse', 'HEAD').stdout.strip(); rel = f'evals/{stage}.jsonl'; committed_clean(rel)
        evsha = hashlib.sha256(subprocess.run(['git', '-C', D, 'show', f'{head}:./{rel}'], capture_output=True).stdout).hexdigest()
        if '--local' in sys.argv:
            assert stage not in SECRETS, 'локальное событие — только для сухого прогона'
            ev = dict(after=head, timestamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), activity_type='local')
        else:
            act = json.loads(subprocess.run(['gh', 'api', 'repos/131ymm-commits/Neu/activity?per_page=50'], capture_output=True, text=True, check=True).stdout)
            ev = next((e for e in act if e.get('after') == head and e.get('activity_type') == 'push'), None)
            assert ev, f'нет серверного события о пуше {head[:7]} — сначала запушить'
        json.dump(dict(note=f'Серверное событие о пуше выборов этапа {stage} PRECOND-02 (до расчёта правды).', commit=head[:7], evals_sha256=evsha, event=ev),
                  open(f'{D}/{stage}_push_activity.json', 'w'), ensure_ascii=False, indent=1)
        print('событие:', ev['timestamp'], head[:7], 'sha256 выборов', evsha[:16])
    elif cmd == 'eval_jobs':
        if stage in PREV: guard_b_jobs(stage)
        jobs = []; miss = missing_pools(stage)
        for t in tids(stage):
            if t in miss: print('нет пула — задача исключена до оценщиков (run/{}_exec_missing.json):'.format(stage), t); continue
            assert os.path.exists(f'{D}/pools/{t}.json'), f'нет пула {t}, а в списке пропусков его нет'
            for a, on in ARMS.items():
                text, schema = prompt_for(on, t)
                jobs += [dict(id=f'{t}|{a}|{i}', prompt=text, schema=schema) for i in range(VOTES)]
        write_jobs(f'{stage}_eval', jobs)
    elif cmd == 'collect_eval':
        os.makedirs(f'{D}/evals', exist_ok=True); n = 0
        with open(f'{D}/evals/{stage}.jsonl', 'w') as fh:
            for lab, r in results(f'{stage}_eval').items():
                t, a, i = lab.split('|'); pm = perm(t); res = r.get('result') or {}; c = res.get('choice')
                ch = None if r.get('error') else (pm[c] if isinstance(c, int) and 0 <= c < len(pm) else c)   # −1 (отказ) и мусор — как есть
                fh.write(json.dumps(dict(task=t, arm=a, i=int(i), choice=ch, shown_choice=c, error=r.get('error'), inp=r.get('inp', 0), out=r.get('out', 0),
                                         models=r.get('models'), retried=r.get('retried', False), effort='medium'), ensure_ascii=False) + '\n'); n += 1
        print(n, 'выборов')
    elif cmd == 'truth':
        guard_truth(stage); sec = sec_for(stage); os.makedirs(f'{sec}/truth', exist_ok=True); slt = salt(sec); n = 0
        for t in tids(stage):
            if os.path.exists(f'{D}/pools/{t}.json'):
                json.dump([sim.truth(task(t), c['plan'], slt) for c in pool(t)], open(f'{sec}/truth/{t}.json', 'w')); n += 1
        print('правда посчитана для', n, 'задач')
