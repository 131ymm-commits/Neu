# SELECT-01: обвязка. Головы запускаются workflow-скриптами, которые строит эта обвязка; правда считается только здесь.
#   python3 harness.py salt                              — создать секретную соль (один раз), напечатать её SHA-256
#   python3 harness.py tasks <WH|SC> <seed0> <n>         — задачи в tasks/ (публичная часть, без шума)
#   python3 harness.py exec <stage> <task_id...>         — run/<stage>.js: исполнитель строит пул k = 8 по каждой задаче
#   python3 harness.py collect_exec <wf_id> <stage>      — pools/<task>.json (+ правда кандидатов в секрет), tokens в run/<stage>_tokens.json
#   python3 harness.py eval <stage> <N> <arms,через,запятую> <task_id...>  — run/<stage>.js: оценщики (N вызовов для рук *_N, B_*)
#   python3 harness.py collect_eval <wf_id> <stage>      — evals/<stage>.jsonl: выбор каждой головы + её токены
# Секрет: /root/select_secret/ (соль шума, правда кандидатов). Головам в промпт идут только правила задачи и планы (с заявкой — для A, B_zayavka).
import glob, hashlib, json, os, secrets, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim, prompts
D = os.environ.get('SELECT_ROOT', os.path.dirname(os.path.abspath(__file__))); SEC = os.environ.get('SELECT_SECRET', '/root/select_secret')
PROJ = os.path.expanduser('~/.claude/projects')
MULTI = {'B_blind', 'B_zayavka', 'C_N', 'D_N'}   # руки из N вызовов

def salt():
    return open(f'{SEC}/salt.txt').read().strip()

def task(tid):
    return json.load(open(f'{D}/tasks/{tid}.json'))

def js(stage, jobs, schema):
    os.makedirs(f'{D}/run', exist_ok=True)
    s = (f"export const meta = {{ name: 'select01-{stage}', description: 'SELECT-01, этап {stage}', phases: [{{ title: 'Ход' }}] }}\n"
         f"const JOBS = {json.dumps(jobs, ensure_ascii=False)}\nconst S = {json.dumps(schema)}\nphase('Ход')\n"
         "const res = await parallel(JOBS.map(j => () => agent(j.prompt, {label: j.id, phase: 'Ход', schema: S}).catch(e => ({error: String(e)}))))\n"
         "const out = {}\nJOBS.forEach((j, i) => { out[j.id] = res[i] })\nreturn {out}\n")
    p = f'{D}/run/{stage}.js'; open(p, 'w').write(s); print(p, len(jobs), 'голов')

def wf_record(wf):
    f = glob.glob(f'{PROJ}/*/workflows/{wf}.json'); return json.load(open(f[0]))

def wf_tokens(wf):
    # токены по меткам голов из транскриптов: вход (с кэшем) и выход, по всем ходам головы
    out = {}
    for d in glob.glob(f'{PROJ}/*/*/subagents/workflows/{wf}'):
        for m in glob.glob(f'{d}/agent-*.meta.json'):
            lab = json.load(open(m)).get('description'); inp = outp = 0; models = set(); tools = 0
            for line in open(m.replace('.meta.json', '.jsonl'), errors='replace'):
                try: o = json.loads(line)
                except ValueError: continue
                msg = o.get('message') or {}
                if o.get('type') == 'assistant' and isinstance(msg, dict):
                    u = msg.get('usage') or {}
                    inp += u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0)
                    outp += u.get('output_tokens', 0); models.add(msg.get('model'))
                    tools += sum(1 for c in msg.get('content') or [] if isinstance(c, dict) and c.get('type') == 'tool_use' and c.get('name') != 'StructuredOutput')
            out[lab] = dict(inp=inp, out=outp, models=sorted(x for x in models if x), tool_calls=tools)
    return out

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'salt':
        os.makedirs(SEC, exist_ok=True); p = f'{SEC}/salt.txt'
        if not os.path.exists(p): open(p, 'w').write(secrets.token_hex(32))
        print('sha256(salt) =', hashlib.sha256(salt().encode()).hexdigest())
    elif cmd == 'tasks':
        typ, s0, n = sys.argv[2], int(sys.argv[3]), int(sys.argv[4]); os.makedirs(f'{D}/tasks', exist_ok=True)
        for s in range(s0, s0 + n):
            json.dump(sim.GEN[typ](s), open(f'{D}/tasks/{typ}_{s}.json', 'w'))
        print(typ, s0, '…', s0 + n - 1)
    elif cmd == 'exec':
        stage, tids = sys.argv[2], sys.argv[3:]
        js(stage, [dict(id=f'{t}|exec', prompt=prompts.EXEC.format(rules=sim.RULES[task(t)['type']](task(t)))) for t in tids], prompts.EXEC_SCHEMA)
    elif cmd == 'collect_exec':
        wf, stage = sys.argv[2], sys.argv[3]; res = wf_record(wf)['result']['out']; tok = wf_tokens(wf)
        os.makedirs(f'{D}/pools', exist_ok=True); os.makedirs(f'{SEC}/truth', exist_ok=True); slt = salt()
        for lab, r in res.items():
            t = lab.split('|')[0]
            if not isinstance(r, dict) or 'candidates' not in r: print('нет пула:', t, str(r)[:200]); continue
            pool = r['candidates'][:8]; json.dump(pool, open(f'{D}/pools/{t}.json', 'w'), ensure_ascii=False)
            tr = [sim.truth(task(t), c['plan'], slt) for c in pool]
            json.dump(tr, open(f'{SEC}/truth/{t}.json', 'w'))
        json.dump(tok, open(f'{D}/run/{stage}_tokens.json', 'w'), ensure_ascii=False, indent=0)
        print('пулов:', len(glob.glob(f'{D}/pools/*.json')))
    elif cmd == 'eval':
        stage, N, arms, tids = sys.argv[2], int(sys.argv[3]), sys.argv[4].split(','), sys.argv[5:]; jobs = []
        for t in tids:
            tk = task(t); pool = json.load(open(f'{D}/pools/{t}.json')); rules = sim.RULES[tk['type']](tk)
            for a in arms:
                for i in range(N if a in MULTI else 1):
                    jobs.append(dict(id=f'{t}|{a}|{i}', prompt=prompts.eval_prompt(a, rules, pool)))
        js(stage, jobs, prompts.EVAL_SCHEMA)
    elif cmd == 'collect_eval':
        wf, stage = sys.argv[2], sys.argv[3]; res = wf_record(wf)['result']['out']; tok = wf_tokens(wf)
        os.makedirs(f'{D}/evals', exist_ok=True)
        with open(f'{D}/evals/{stage}.jsonl', 'w') as fh:
            for lab, r in res.items():
                t, a, i = lab.split('|'); ch = r.get('choice') if isinstance(r, dict) else None
                fh.write(json.dumps(dict(task=t, arm=a, i=int(i), choice=ch, error=None if ch is not None else str(r)[:200], **tok.get(lab, {})), ensure_ascii=False) + '\n')
        print(len(res), 'выборов')
