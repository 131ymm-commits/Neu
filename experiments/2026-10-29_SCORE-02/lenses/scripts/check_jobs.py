# Пересчёт заданий SCORE-02 независимым кодом: перестановка, промпт, схема, число вызовов, байты; сверка с пилотом 3 SCORE-01.
import hashlib, json, os, random, sys, collections
ROOT = '/home/claude/neu'
EXP = f'{ROOT}/experiments'
S2 = f'{EXP}/2026-10-29_SCORE-02'
SEL = f'{EXP}/2026-10-07_SELECT-01'
SC1 = f'{EXP}/2026-10-28_SCORE-01'
sys.path.insert(0, SEL); sys.path.insert(0, SC1)
import sim, prompts_score as P
SRC = dict(pilot=SEL, main=f'{EXP}/2026-10-15_THINK-01', rep=f'{EXP}/2026-10-21_PRECOND-01')
def tasks_dir(src): return sorted(os.listdir(f'{src}/tasks'))
for nm, src in SRC.items():
    ts = [f[:-5] for f in os.listdir(f'{src}/pools') if f.startswith('WH_')]
    print(nm, 'пулов WH:', len(ts), 'диапазон', min(ts), max(ts))
def myperm(seed):
    p = list(range(8)); random.Random(int(hashlib.sha256(f'{seed}|perm'.encode()).hexdigest()[:16], 16)).shuffle(p); return p
def check(jobs_path, src, ids):
    J = [json.loads(l) for l in open(jobs_path, encoding='utf-8')]
    by = collections.defaultdict(list)
    for j in J: by[j['task']].append(j)
    bad = 0; nb = []
    exp_tasks = [f'WH_{s}' for s in ids if os.path.exists(f'{src}/pools/WH_{s}.json')]
    assert sorted(by) == sorted(exp_tasks), (len(by), len(exp_tasks))
    for t, js in by.items():
        tk = json.load(open(f'{src}/tasks/{t}.json')); pl = json.load(open(f'{src}/pools/{t}.json'))
        pm = myperm(tk['seed']); shown = [pl[j] for j in pm]
        pr = P.prompt_half('LOG', sim.RULES['WH'](tk), shown)
        ids_k = sorted(j['id'] for j in js)
        if ids_k != [f'{t}|LOG|{k}' for k in range(5)]: bad += 1; print('id', t, ids_k)
        for j in js:
            if j['prompt'] != pr: bad += 1; print('prompt', j['id'])
            if j['schema'] != P.SCHEMA_H: bad += 1; print('schema', j['id'])
            if j.get('arm') != 'LOG': bad += 1
        nb.append(len(pr.encode()))
        assert len(pl) == 8, t
    print(os.path.basename(jobs_path), 'заданий', len(J), 'задач', len(by), 'расхождений', bad, 'байты', min(nb), max(nb))
    return by
check(f'{S2}/jobs/main_jobs.jsonl', SRC['main'], range(8201, 8301))
check(f'{S2}/jobs/rep_jobs.jsonl', SRC['rep'], range(8301, 8360))
check(f'{S2}/run/pilot_jobs.jsonl', SRC['pilot'], list(range(7001, 7013)) + list(range(7301, 7309)))
# сверка с пилотом 3 SCORE-01 (рука LOG)
p3 = [json.loads(l) for l in open(f'{SC1}/run/pilot3_jobs.jsonl', encoding='utf-8')]
p3log = {}
for j in p3:
    t, arm, k = j['id'].split('|')
    if arm == 'LOG': p3log.setdefault(t, set()).add(hashlib.sha256(j['prompt'].encode()).hexdigest())
pj = [json.loads(l) for l in open(f'{S2}/run/pilot_jobs.jsonl', encoding='utf-8')]
same = sum(1 for t in {j['task'] for j in pj} if {hashlib.sha256(j['prompt'].encode()).hexdigest() for j in pj if j['task'] == t} <= p3log.get(t, set()))
print('пилот: задач с промптом, равным LOG пилота 3 SCORE-01:', same, 'из', len({j['task'] for j in pj}))
# сиды задач: пересечения между выборками
seeds = {}
for nm, src, ids in (('pilot', SRC['pilot'], list(range(7001, 7013)) + list(range(7301, 7309))), ('main', SRC['main'], range(8201, 8301)), ('rep', SRC['rep'], range(8301, 8360))):
    for s in ids:
        p = f'{src}/tasks/WH_{s}.json'
        if os.path.exists(p) and os.path.exists(f'{src}/pools/WH_{s}.json'):
            seeds.setdefault(json.load(open(p))['seed'], []).append((nm, s))
dup = {k: v for k, v in seeds.items() if len(v) > 1}
print('повторов сида задачи между/внутри выборок:', len(dup), list(dup.items())[:5])
print('хеши промпта:', {k: v[:8] for k, v in P.hashes().items() if k in ('ROLE_H', 'LOG_H', 'schema_H')})
