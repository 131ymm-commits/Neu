# «Арена» (совет 17): сборка раундов, приёмка задач кодом, подсчёт слоёв, меток и типов ошибок.
#   python3 arena.py attack <r>            → rounds/r<r>/attack.js           (нападающие; история из прошлых раундов)
#   python3 arena.py accept <r> <out.json> → rounds/r<r>/tasks.json, fix.js (приёмка: интерпретатор + CPython; одна бесплатная попытка)
#   python3 arena.py merge_fix <r> <out.json>
#   python3 arena.py defend <r>            → rounds/r<r>/defend.js           (панель ×3 + одиночка замороженный + учащийся + команда)
#   python3 arena.py score <r> <out.json>  → rounds/r<r>/score.json
import json, os, sys, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from interp import run
from sandbox import run_py
import prompts as P
K = 6; ATT = 2; NT = 5
def rd(r): d = os.path.join(HERE, 'rounds', f'r{r}'); os.makedirs(d, exist_ok=True); return d
def J(path): return json.load(open(path))
def W(path, obj): json.dump(obj, open(path, 'w'), ensure_ascii=False, indent=1)
def unwrap(path):
    d = J(path); return d.get('out', d)

def wf(name, desc, jobs, schemas):
    return (f"export const meta = {{ name: '{name}', description: '{desc}', phases: [{{ title: 'Ход' }}] }}\n"
            f"const JOBS = {json.dumps(jobs, ensure_ascii=False)}\nconst S = {json.dumps(schemas, ensure_ascii=False)}\nphase('Ход')\n"
            "const res = await parallel(JOBS.map(j => () => agent(j.prompt, {label: j.id, phase: 'Ход', schema: S[j.schema]})))\n"
            "const out = {}\nJOBS.forEach((j, i) => { out[j.id] = res[i] })\nreturn {out}\n")
TASK_S = {'type': 'object', 'properties': {'title': {'type': 'string'}, 'prose': {'type': 'string'}, 'rules': {'type': 'string'}, 'battle': {'type': 'object'},
          'examples': {'type': 'array', 'items': {'type': 'object'}}, 'bet': {'type': 'string'}}, 'required': ['title', 'prose', 'rules', 'battle', 'examples', 'bet']}
ATT_S = {'type': 'object', 'properties': {'tasks': {'type': 'array', 'items': TASK_S}}, 'required': ['tasks']}
ALT_S = {'type': 'object', 'properties': {'found': {'type': 'boolean'}, 'rules': {'type': 'string'}, 'reading': {'type': 'string'}}, 'required': ['found', 'rules', 'reading']}
TR_S = {'type': 'object', 'properties': {'rules': {'type': 'string'}, 'doubts': {'type': 'string'}}, 'required': ['rules', 'doubts']}
DEF_S = {'type': 'object', 'properties': {'answer': {'type': 'string'}, 'program': {'type': 'string'}, 'runs': {'type': 'integer'}}, 'required': ['answer', 'program', 'runs']}
CHK_S = {'type': 'object', 'properties': {'answer': {'type': 'string'}, 'program': {'type': 'string'}, 'runs': {'type': 'integer'}, 'changed': {'type': 'boolean'}}, 'required': ['answer', 'program', 'runs', 'changed']}

def history(r, k):
    h = []
    for q in range(1, r):
        s = os.path.join(rd(q), 'score.json')
        if not os.path.exists(s): continue
        for t in J(s)['tasks']:
            if t['attacker'] != k: continue
            o = ('снята (двусмысленная или нечестная), −2' if t['status'] == 'removed' else
                 'не принята (правила не исполнились или не уложились в лимит)' if t['status'] == 'invalid' else
                 'защитник ошибся — +1' if t['solo']['counted'] else 'защитник ответил верно — 0' if t['solo']['ok'] else 'защитник не уложился в ресурс или ошибся в формате — 0')
            h.append(dict(round=q, title=t['title'], outcome=o))
    return h

def attack(r):
    jobs = [dict(id=f'att{k}_r{r}', schema='A', prompt=P.attacker(k, r, history(r, k))) for k in range(1, ATT + 1)]
    open(os.path.join(rd(r), 'attack.js'), 'w').write(wf(f'arena-attack-r{r}', f'Арена, раунд {r}: нападающие', jobs, {'A': ATT_S}))

def check_task(t):
    """приёмка кодом: интерпретатор и CPython на боевом входе и примерах → (ok, сообщение, правда, примеры)"""
    if not isinstance(t.get('battle'), dict) or not t.get('examples'): return False, 'нет боевого входа или примеров', None, None
    if not (2 <= len(t['examples']) <= 3): return False, 'нужно 2–3 примера', None, None
    res = []
    for p in [t['battle']] + list(t['examples']):
        a = run(t['rules'], p)
        if a[0] != 'ok': return False, f'интерпретатор: {a[0]}: {a[1]}', None, None
        b = run_py(t['rules'], p)
        if b[0] != 'ok': return False, f'CPython: {b[0]}: {b[1]}', None, None
        if a[1] != b[1]: return False, 'DEFECT: интерпретатор и CPython разошлись', None, None
        res.append(a[1])
    return True, 'ok', res[0], [dict(p=p, ans=v) for p, v in zip(t['examples'], res[1:])]

def accept(r, path):
    out = unwrap(path); tasks = []; fix = []
    for k in range(1, ATT + 1):
        sub = (out.get(f'att{k}_r{r}') or {}).get('tasks', [])[:NT]
        for i, t in enumerate(sub):
            tid = f'r{r}a{k}t{i}'; ok, msg, truth, ex = check_task(t)
            tasks.append(dict(tid=tid, attacker=k, round=r, **{x: t.get(x) for x in ('title', 'prose', 'rules', 'battle', 'bet')}, examples_in=t.get('examples'),
                              examples=ex, truth=truth, accept=msg, fixed=False))
            if not ok and not msg.startswith('DEFECT'):
                fix.append(dict(id=f'fix_{tid}', schema='T', prompt=P.attacker(k, r, []).split('Сдай ровно 5 задач.')[0] +
                    f"Твоя задача «{t.get('title')}» не прошла приёмку: {msg}. У тебя одна попытка исправить её. Сдай исправленную задачу (одну) в том же формате.\n\nИсходная задача:\n{json.dumps(t, ensure_ascii=False)[:6000]}"))
    W(os.path.join(rd(r), 'tasks.json'), tasks)
    if fix: open(os.path.join(rd(r), 'fix.js'), 'w').write(wf(f'arena-fix-r{r}', f'Арена, раунд {r}: исправление задач', fix, {'T': TASK_S}))
    print('задач', len(tasks), 'принято кодом', sum(t['accept'] == 'ok' for t in tasks), 'на исправление', len(fix), 'дефектов прибора', sum(t['accept'].startswith('DEFECT') for t in tasks))

def merge_fix(r, path):
    out = unwrap(path); tasks = J(os.path.join(rd(r), 'tasks.json'))
    for t in tasks:
        f = out.get(f"fix_{t['tid']}")
        if t['accept'] == 'ok' or not f: continue
        ok, msg, truth, ex = check_task(f)
        t.update({x: f.get(x) for x in ('title', 'prose', 'rules', 'battle', 'bet')}, examples_in=f.get('examples'), examples=ex, truth=truth, accept=msg, fixed=True)
    W(os.path.join(rd(r), 'tasks.json'), tasks)
    print('принято кодом после исправления', sum(t['accept'] == 'ok' for t in tasks), 'из', len(tasks))

def learn_hist(r):
    h = []
    for q in range(1, r):
        s = os.path.join(rd(q), 'score.json')
        if not os.path.exists(s): continue
        for t in J(s)['tasks']:
            if t['status'] == 'fair' and t.get('learn'):
                L = t['learn']; h.append(dict(title=t['title'], given=L['given'], truth=t['truth'], kind='верно' if L['ok'] else f"ошибка: {L['kind']}"))
    return h

def defend(r):
    tasks = [t for t in J(os.path.join(rd(r), 'tasks.json')) if t['accept'] == 'ok']; jobs = []; team = []
    for t in tasks:
        for j in range(3): jobs.append(dict(id=f"{t['tid']}|alt{j}", schema='ALT', prompt=P.alt_reader(t, j)))
        jobs.append(dict(id=f"{t['tid']}|solo", schema='D', prompt=P.solo(t, 2 * K, None, 'solo')))
        jobs.append(dict(id=f"{t['tid']}|learn", schema='D', prompt=P.solo(t, 2 * K, learn_hist(r), 'learn')))
        mark = '@@SOL@@'; c = P.checker(t, K, {'answer': mark, 'program': mark})
        a, b, rest = c.split(mark, 2)[0], c.split(mark, 2)[1], c.split(mark, 2)[2]
        team.append(dict(id=t['tid'], solver=P.solo(t, K, None, 'team1'), c1=a, c2=b, c3=rest))
    js = (f"export const meta = {{ name: 'arena-defend-r{r}', description: 'Арена, раунд {r}: панель, одиночки и команда', phases: [{{ title: 'Ход' }}] }}\n"
          f"const JOBS = {json.dumps(jobs, ensure_ascii=False)}\nconst TEAM = {json.dumps(team, ensure_ascii=False)}\nconst S = {json.dumps({'ALT': ALT_S, 'D': DEF_S, 'C': CHK_S}, ensure_ascii=False)}\nphase('Ход')\n"
          "const out = {}\n"
          "const th = TEAM.map(t => async () => { const s = await agent(t.solver, {label: t.id + '|team1', phase: 'Ход', schema: S.D}); out[t.id + '|team1'] = s;\n"
          "  const c = await agent(t.c1 + String(s ? s.answer : '') + t.c2 + String(s ? s.program : '') + t.c3, {label: t.id + '|chk', phase: 'Ход', schema: S.C}); out[t.id + '|chk'] = c })\n"
          "const jh = JOBS.map(j => async () => { out[j.id] = await agent(j.prompt, {label: j.id, phase: 'Ход', schema: S[j.schema]}) })\n"
          "await parallel([...th, ...jh])\nreturn {out}\n")
    open(os.path.join(rd(r), 'defend.js'), 'w').write(js)
    print('задач', len(tasks), 'вызовов', len(jobs) + 2 * len(team), 'байт', len(js.encode()))

def check_stage(r, path):
    out = unwrap(path); tasks = [t for t in J(os.path.join(rd(r), 'tasks.json')) if t['accept'] == 'ok']
    jobs = [dict(id=f"{t['tid']}|chk", schema='C', prompt=P.checker(t, K, out.get(f"{t['tid']}|team1") or {})) for t in tasks]
    open(os.path.join(rd(r), 'check.js'), 'w').write(wf(f'arena-check-r{r}', f'Арена, раунд {r}: сверщики команды', jobs, {'C': CHK_S}))
    print('сверщиков', len(jobs))

def ans_int(s):
    s = str(s or '').strip().replace(' ', '').replace('−', '-')
    try: return int(s)
    except ValueError: return None
def judge_def(t, d):
    """метка и тип ошибки защитника по коду"""
    if not d: return dict(ok=False, given=None, kind='нет ответа', counted=False)
    g = ans_int(d.get('answer'))
    if g is None: return dict(ok=False, given=d.get('answer'), kind='формат', counted=False)
    if g == t['truth']: return dict(ok=True, given=g, kind='верно', counted=False)
    prog = d.get('program') or ''
    pb = run_py(prog, t['battle'], cpu_s=20, mem_mb=1024)
    pex = [run_py(prog, e['p'], cpu_s=20, mem_mb=1024) for e in t['examples']]
    if pb[0] == 'ok' and pb[1] != t['truth']: kind = 'формализация'            # программа считает не то
    elif pb[0] == 'ok' and pb[1] == t['truth']: kind = 'переписывание/счёт'    # программа верна, сдан другой ответ
    elif pb[0] == 'limit': kind = 'ресурс'
    else: kind = 'формализация (программа не исполняется)' if all(x[0] != 'ok' or x[1] == e['ans'] for x, e in zip(pex, t['examples'])) else 'формализация'
    ex_ok = all(x[0] == 'ok' and x[1] == e['ans'] for x, e in zip(pex, t['examples']))
    return dict(ok=False, given=g, kind=kind, counted=kind != 'ресурс', ex_ok=ex_ok)

def score(r, path_def, path_chk):
    out = unwrap(path_def); chk = unwrap(path_chk) if path_chk else {}; tasks = J(os.path.join(rd(r), 'tasks.json')); res = []
    for t in tasks:
        e = dict(tid=t['tid'], attacker=t['attacker'], round=r, title=t['title'], truth=t['truth'], bet=t['bet'], accept=t['accept'])
        if t['accept'] != 'ok':
            e['status'] = 'defect' if t['accept'].startswith('DEFECT') else 'invalid'; e['points'] = 0; res.append(e); continue
        alts = []
        for j in range(3):
            x = out.get(f"{t['tid']}|alt{j}") or {}
            if x.get('found') and x.get('rules'):
                b = run_py(x['rules'], t['battle']); exs = [run_py(x['rules'], q['p']) for q in t['examples']]
                valid = b[0] == 'ok' and b[1] != t['truth'] and all(z[0] == 'ok' and z[1] == q['ans'] for z, q in zip(exs, t['examples']))
                alts.append(dict(found=True, valid=valid, battle=b[1] if b[0] == 'ok' else b[0], reading=x.get('reading', '')))
            else: alts.append(dict(found=False, valid=False, reading=x.get('reading', '')))
        e['panel'] = alts; e['alt_valid'] = sum(z['valid'] for z in alts)
        e['status'] = 'removed' if e['alt_valid'] else 'fair'
        e['solo'] = judge_def(t, out.get(f"{t['tid']}|solo")); e['learn'] = judge_def(t, out.get(f"{t['tid']}|learn"))
        e['team_solver'] = judge_def(t, out.get(f"{t['tid']}|team1")); e['team'] = judge_def(t, out.get(f"{t['tid']}|chk"))
        e['team_changed'] = (out.get(f"{t['tid']}|chk") or {}).get('changed')
        e['points'] = -2 if e['status'] == 'removed' else (1 if e['solo']['counted'] else 0)
        res.append(e)
    W(os.path.join(rd(r), 'score.json'), dict(round=r, tasks=res))
    for e in res:
        s = e.get('solo', {}); tm = e.get('team', {})
        print(e['tid'], e['status'], e.get('alt_valid'), 'одиночка', s.get('kind'), '| учащийся', e.get('learn', {}).get('kind'), '| команда', tm.get('kind'), '| очки', e['points'], '|', e['title'][:40])

if __name__ == '__main__':
    c = sys.argv[1]; r = int(sys.argv[2])
    if c == 'attack': attack(r)
    elif c == 'accept': accept(r, sys.argv[3])
    elif c == 'merge_fix': merge_fix(r, sys.argv[3])
    elif c == 'defend': defend(r)
    elif c == 'check': check_stage(r, sys.argv[3])
    elif c == 'score': score(r, sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
