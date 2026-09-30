# «Арена стихов» (совет 18): заказы нападающих, приёмка кодом, панель честности, защитники 2×2 с двумя попытками, слепая тема.
#   python3 poem_arena.py attack <r>                → rounds/r<r>/attack.js
#   python3 poem_arena.py accept <r> <out.json>     → rounds/r<r>/orders.json (+ fix.js)
#   python3 poem_arena.py merge_fix <r> <out.json>
#   python3 poem_arena.py stage1 <r>                → rounds/r<r>/stage1.js (панель + попытка 1 всех рук)
#   python3 poem_arena.py stage2 <r> <out1.json>    → rounds/r<r>/stage2.js (попытка 2 с обратной связью + слепая тема по попытке 1-го не нужна)
#   python3 poem_arena.py stage3 <r> <out2.json>    → rounds/r<r>/stage3.js (слепая тема по итоговым стихам и калибровка)
#   python3 poem_arena.py score <r> <out1> <out2> <out3> → rounds/r<r>/score.json
import json, os, sys, random, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from poemlib import LIB, base_ok, lines, words, letters
from interp import run_check
from sandbox import run_check_py
import poem_prompts as P
ATT = int(os.environ.get('POEM_ATT', 2)); NO = int(os.environ.get('POEM_NO', 4)); MAX_REP = 3; MIN_REJECT = 0.5
ARMS = ['solo', 'team', 'solo_lib', 'team_lib']
def rd(r): d = os.path.join(HERE, os.environ.get('POEM_DIR', 'rounds'), f'r{r}'); os.makedirs(d, exist_ok=True); return d
def J(p): return json.load(open(p))
def W(p, o): json.dump(o, open(p, 'w'), ensure_ascii=False, indent=1)
def unwrap(p): d = J(p); return d.get('out', d)
ORDER_S = {'type': 'object', 'properties': {'title': {'type': 'string'}, 'theme': {'type': 'string'}, 'kind': {'type': 'string'}, 'items': {'type': 'array', 'items': {'type': 'string'}},
           'checks': {'type': 'array', 'items': {'type': 'string'}}, 'witness': {'type': 'string'}, 'bet': {'type': 'string'}},
           'required': ['title', 'theme', 'kind', 'items', 'checks', 'witness', 'bet']}
ATT_S = {'type': 'object', 'properties': {'orders': {'type': 'array', 'items': ORDER_S}}, 'required': ['orders']}
CHK2_S = {'type': 'object', 'properties': {'checks': {'type': 'array', 'items': {'type': 'string'}}}, 'required': ['checks']}
ALT_S = {'type': 'object', 'properties': {'poems': {'type': 'array', 'items': {'type': 'string'}}, 'note': {'type': 'string'}}, 'required': ['poems', 'note']}
POEM_S = {'type': 'object', 'properties': {'poem': {'type': 'string'}, 'lib_calls': {'type': 'integer'}}, 'required': ['poem', 'lib_calls']}
TOPIC_S = {'type': 'object', 'properties': {'choice': {'type': 'integer'}}, 'required': ['choice']}

def items_src(checks):
    """пункты проверки: список функций item(poem) → программа с item1..itemK и check()"""
    out = []
    for i, c in enumerate(checks, 1):
        c = c.strip()
        c = re.sub(r'^def\s+\w+\s*\(', f'def item{i}(', c, count=1)
        out.append(c)
    out.append('def check(poem):\n    return ' + ' and '.join(f'item{i}(poem)' for i in range(1, len(checks) + 1)))
    return '\n\n'.join(out)
def verdicts(checks, poem):
    """→ (True, []) | (False, [номера нарушенных пунктов]) по интерпретатору; ошибка исполнения — ('err', сообщение)"""
    base = items_src(checks).rsplit('\n\ndef check(poem)', 1)[0]; failed = []
    for i in range(1, len(checks) + 1):
        a = run_check(base + f'\n\ndef check(poem):\n    return item{i}(poem)\n', poem, LIB)
        if a[0] != 'ok': return 'err', f'пункт {i}: {a[0]}: {a[1]}'
        if not a[1]: failed.append(i)
    return (not failed), failed
def distort(poem, n, rng):
    L = lines(poem); out = set()
    ops = ['letter_swap', 'letter_del', 'letter_ins', 'word_del', 'word_dup', 'line_swap', 'line_del', 'line_dup']
    tries = 0
    while len(out) < n and tries < n * 20:
        tries += 1; op = rng.choice(ops); M = [list(x) for x in L]
        i = rng.randrange(len(M))
        if op.startswith('letter'):
            pos = [j for j, c in enumerate(M[i]) if re.match(r'[а-яёА-ЯЁ]', c)]
            if not pos: continue
            j = rng.choice(pos)
            if op == 'letter_swap': M[i][j] = rng.choice('аеиоуыябвгдклмнпрст')
            elif op == 'letter_del': M[i].pop(j)
            else: M[i].insert(j, rng.choice('аеиоуыябвгдклмнпрст'))
            txt = '\n'.join(''.join(x) for x in M)
        elif op.startswith('word'):
            ws = ''.join(M[i]).split(' ')
            if len(ws) < 2: continue
            k = rng.randrange(len(ws))
            if op == 'word_del': ws.pop(k)
            else: ws.insert(k, ws[k])
            M[i] = list(' '.join(ws)); txt = '\n'.join(''.join(x) for x in M)
        else:
            S = [''.join(x) for x in M]
            if op == 'line_swap' and len(S) > 1: k = rng.randrange(len(S) - 1); S[k], S[k + 1] = S[k + 1], S[k]
            elif op == 'line_del' and len(S) > 2: S.pop(i)
            elif op == 'line_dup': S.insert(i, S[i])
            else: continue
            txt = '\n'.join(S)
        if txt != poem: out.add(txt)
    return sorted(out)

def history(r, k):
    h = []
    for q in range(1, r):
        s = os.path.join(rd(q), 'score.json')
        if not os.path.exists(s): continue
        for o in J(s)['orders']:
            if o['attacker'] != k: continue
            if o['status'] != 'fair': h.append(dict(title=o['title'], outcome=f"снят ({o['status']}) — 0")); continue
            fails = sum(not o['arms'][a]['final_ok'] for a in ARMS)
            h.append(dict(title=o['title'], outcome=f"защитники провалили {fails} из 4 рук (итоговая попытка) — +{fails}"))
    return h
def attack(r):
    jobs = [dict(id=f'att{k}_r{r}', schema='A', prompt=P.attacker(k, r, NO, history(r, k))) for k in range(1, ATT + 1)]
    tag = os.environ.get('POEM_DIR', 'rounds')
    open(os.path.join(rd(r), 'attack.js'), 'w').write(wf(f'poem-{tag}-attack-r{r}', f'Арена стихов ({tag}), раунд {r}: нападающие', jobs, {'A': ATT_S}))
def wf(name, desc, jobs, schemas):
    return (f"export const meta = {{ name: '{name}', description: '{desc}', phases: [{{ title: 'Ход' }}] }}\n"
            f"const JOBS = {json.dumps(jobs, ensure_ascii=False)}\nconst S = {json.dumps(schemas, ensure_ascii=False)}\nphase('Ход')\n"
            "const res = await parallel(JOBS.map(j => () => agent(j.prompt, {label: j.id, phase: 'Ход', schema: S[j.schema]})))\n"
            "const out = {}\nJOBS.forEach((j, i) => { out[j.id] = res[i] })\nreturn {out}\n")

def check_order(o):
    if not (2 <= len(o.get('items') or []) <= 8) or len(o['items']) != len(o.get('checks') or []): return False, 'пунктов прозы и проверок должно быть поровну, 2–8'
    w = o.get('witness') or ''
    v = verdicts(o['checks'], w)
    if v[0] == 'err': return False, 'интерпретатор: ' + v[1]
    b = run_check_py(items_src(o['checks']), w, HERE)
    if b[0] != 'ok': return False, 'CPython: ' + str(b[1])
    if b[1] != v[0]: return False, 'DEFECT: интерпретатор и CPython разошлись'
    if not v[0]: return False, f'свидетель не проходит собственную проверку (пункты {v[1]})'
    ok, bad = base_ok(w, MAX_REP)
    if not ok: return False, f'свидетель не проходит базовое условие (слова не из словаря: {bad[:8]}, повторы, ≥ 2 строк)'
    dist = distort(w, 30, random.Random(hash(w) % 2**32))
    rej = sum(1 for d in dist if not run_check(items_src(o['checks']), d, LIB)[1]) / max(1, len(dist))
    o['reject_share'] = rej
    if rej < MIN_REJECT: return False, f'проверка слишком слабая: отвергает {rej:.0%} искажений свидетеля (нужно ≥ {MIN_REJECT:.0%})'
    return True, 'ok'
def accept(r, path):
    out = unwrap(path); orders = []; fix = []
    for k in range(1, ATT + 1):
        for i, o in enumerate(((out.get(f'att{k}_r{r}') or {}).get('orders') or [])[:NO]):
            oid = f'r{r}a{k}o{i}'; ok, msg = check_order(o)
            orders.append(dict(oid=oid, attacker=k, round=r, **{x: o.get(x) for x in ('title', 'theme', 'kind', 'items', 'checks', 'witness', 'bet')}, reject_share=o.get('reject_share'), accept=msg, fixed=False))
            if not ok and not msg.startswith('DEFECT'):
                fix.append(dict(id=f'fix_{oid}', schema='O', prompt=P.fix(k, r, o, msg)))
    W(os.path.join(rd(r), 'orders.json'), orders)
    if fix: open(os.path.join(rd(r), 'fix.js'), 'w').write(wf(f'poem-fix-r{r}', f'Арена стихов, раунд {r}: исправление заказов', fix, {'O': ORDER_S}))
    print('заказов', len(orders), 'принято', sum(o['accept'] == 'ok' for o in orders), 'на исправление', len(fix))
    for o in orders: print(' ', o['oid'], o['accept'][:110], '|', o['title'])
def merge_fix(r, path):
    out = unwrap(path); orders = J(os.path.join(rd(r), 'orders.json'))
    for o in orders:
        f = out.get(f"fix_{o['oid']}")
        if o['accept'] == 'ok' or not f: continue
        ok, msg = check_order(f)
        o.update({x: f.get(x) for x in ('title', 'theme', 'kind', 'items', 'checks', 'witness', 'bet')}, reject_share=f.get('reject_share'), accept=msg, fixed=True)
    W(os.path.join(rd(r), 'orders.json'), orders)
    print('принято после исправления', sum(o['accept'] == 'ok' for o in orders), 'из', len(orders))

def team_js(name, desc, jobs, pipes, schemas):
    """jobs — независимые вызовы; pipes — пары «первый → второй», второй промпт собирается из частей с ответом первого"""
    return (f"export const meta = {{ name: '{name}', description: '{desc}', phases: [{{ title: 'Ход' }}] }}\n"
            f"const JOBS = {json.dumps(jobs, ensure_ascii=False)}\nconst PIPES = {json.dumps(pipes, ensure_ascii=False)}\nconst S = {json.dumps(schemas, ensure_ascii=False)}\nphase('Ход')\nconst out = {{}}\n"
            "const ph = PIPES.map(t => async () => { const a = await agent(t.first, {label: t.id + '|1', phase: 'Ход', schema: S.P}); out[t.id + '|1'] = a;\n"
            "  const b = await agent(t.pre + String(a ? a.poem : '(стихотворения нет)') + t.post, {label: t.id + '|2', phase: 'Ход', schema: S.P}); out[t.id + '|2'] = b })\n"
            "const jh = JOBS.map(j => async () => { out[j.id] = await agent(j.prompt, {label: j.id, phase: 'Ход', schema: S[j.schema]}) })\n"
            "await parallel([...ph, ...jh])\nreturn {out}\n")
MARK = '@@POEM@@'
def arm_pipe(o, arm, att, fb=None, prev=None):
    """одна попытка руки: два вызова (одиночка: написать → пересмотреть своё; команда: поэт → редактор)"""
    lib1 = arm == 'solo_lib'; lib2 = arm in ('solo_lib', 'team_lib')
    first = P.poet(o, lib1, arm, att, fb, prev)
    second = P.reviser(o, lib2, arm, att, fb, MARK) if arm.startswith('solo') else P.editor(o, lib2, arm, att, fb, MARK)
    pre, post = second.split(MARK)
    return dict(id=f"{o['oid']}|{arm}|a{att}", first=first, pre=pre, post=post)
def stage1(r):
    orders = [o for o in J(os.path.join(rd(r), 'orders.json')) if o['accept'] == 'ok']; jobs = []; pipes = []
    for o in orders:
        jobs.append(dict(id=f"{o['oid']}|chk2", schema='C', prompt=P.checker2(o)))
        for j in range(2): jobs.append(dict(id=f"{o['oid']}|alt{j}", schema='ALT', prompt=P.alt(o, j)))
        for arm in ARMS: pipes.append(arm_pipe(o, arm, 1))
    open(os.path.join(rd(r), 'stage1.js'), 'w').write(team_js(f'poem-stage1-r{r}', f'Арена стихов, раунд {r}: панель и попытка 1', jobs, pipes, {'C': CHK2_S, 'ALT': ALT_S, 'P': POEM_S}))
    print('заказов', len(orders), 'вызовов', len(jobs) + 2 * len(pipes))
def final_poem(out, oid, arm, att): return ((out.get(f'{oid}|{arm}|a{att}|2') or {}).get('poem') or (out.get(f'{oid}|{arm}|a{att}|1') or {}).get('poem') or '')
def stage2(r, p1):
    out = unwrap(p1); orders = [o for o in J(os.path.join(rd(r), 'orders.json')) if o['accept'] == 'ok']; pipes = []; fb_all = {}
    for o in orders:
        for arm in ARMS:
            poem = final_poem(out, o['oid'], arm, 1); ok, failed = verdicts(o['checks'], poem) if poem else (False, [0])
            bo, bad = base_ok(poem, MAX_REP)
            fb = dict(ok=bool(ok is True and bo), failed=failed if ok is not True else [], base_bad=bad[:6], base_ok=bo)
            fb_all[f"{o['oid']}|{arm}"] = fb
            if not fb['ok']: pipes.append(arm_pipe(o, arm, 2, fb, poem))
    W(os.path.join(rd(r), 'feedback1.json'), fb_all)
    open(os.path.join(rd(r), 'stage2.js'), 'w').write(team_js(f'poem-stage2-r{r}', f'Арена стихов, раунд {r}: попытка 2 после обратной связи', [], pipes, {'P': POEM_S}))
    print('попыток 2', len(pipes), 'вызовов', 2 * len(pipes))
def stage3(r, p1, p2):
    o1 = unwrap(p1); o2 = unwrap(p2) if p2 and os.path.exists(p2) else {}; orders = [o for o in J(os.path.join(rd(r), 'orders.json')) if o['accept'] == 'ok']
    themes = [o['theme'] for o in orders]; jobs = []; key = {}
    for o in orders:
        rng = random.Random(o['oid']); others = [t for t in themes if t != o['theme']]
        texts = {arm: (final_poem(o2, o['oid'], arm, 2) or final_poem(o1, o['oid'], arm, 1)) for arm in ARMS}
        L = lines(o['witness']); sh = L[:]; random.Random(o['oid'] + 's').shuffle(sh)
        texts['witness'] = o['witness']; texts['witness_shuffled'] = '\n'.join(sh)
        for name, txt in texts.items():
            if not txt: continue
            opts = rng.sample(others, min(4, len(others))) + [o['theme']]; rng.shuffle(opts)
            key[f"{o['oid']}|topic|{name}"] = opts.index(o['theme']) + 1
            jobs.append(dict(id=f"{o['oid']}|topic|{name}", schema='T', prompt=P.topic(txt, opts)))
    W(os.path.join(rd(r), 'topic_key.json'), key)
    open(os.path.join(rd(r), 'stage3.js'), 'w').write(wf(f'poem-stage3-r{r}', f'Арена стихов, раунд {r}: слепое узнавание темы', jobs, {'T': TOPIC_S}))
    print('вызовов', len(jobs))

def score(r, p1, p2, p3):
    o1 = unwrap(p1); o2 = unwrap(p2) if p2 and os.path.exists(p2) else {}; o3 = unwrap(p3) if p3 and os.path.exists(p3) else {}
    key = J(os.path.join(rd(r), 'topic_key.json')) if os.path.exists(os.path.join(rd(r), 'topic_key.json')) else {}
    orders = J(os.path.join(rd(r), 'orders.json')); res = []
    # пул текстов для сверки проверок: свидетели всех заказов, искажения, стихи панели и защитников
    pool_all = [o['witness'] for o in orders if o['accept'] == 'ok']
    for o in orders:
        e = dict(oid=o['oid'], attacker=o['attacker'], title=o['title'], kind=o['kind'], theme=o['theme'], bet=o['bet'], accept=o['accept'], reject_share=o.get('reject_share'))
        if o['accept'] != 'ok': e['status'] = 'invalid'; res.append(e); continue
        c2 = (o1.get(f"{o['oid']}|chk2") or {}).get('checks') or []
        alts = sum(((o1.get(f"{o['oid']}|alt{j}") or {}).get('poems') or [] for j in range(2)), [])
        arms_txt = [final_poem(o1, o['oid'], a, 1) for a in ARMS] + [final_poem(o2, o['oid'], a, 2) for a in ARMS]
        pool = [o['witness']] + distort(o['witness'], 30, random.Random(hash(o['witness']) % 2**32)) + pool_all + alts + [t for t in arms_txt if t]
        dis = []
        if len(c2) != len(o['checks']): dis.append('число пунктов у независимой проверки другое')
        else:
            for t in pool:
                a = verdicts(o['checks'], t); b = verdicts(c2, t)
                if a[0] == 'err': continue
                if b[0] == 'err': dis.append('независимая проверка не исполняется: ' + b[1][:80]); break
                if a != b: dis.append(dict(text=t[:200], attacker=a, independent=b))
        e['disagree'] = dis[:5]; e['n_disagree'] = len(dis)
        e['status'] = 'removed' if dis else 'fair'
        arms = {}
        for arm in ARMS:
            p_1 = final_poem(o1, o['oid'], arm, 1); v1 = verdicts(o['checks'], p_1) if p_1 else (False, [0]); b1 = base_ok(p_1, MAX_REP)[0] if p_1 else False
            ok1 = v1[0] is True and b1
            p_2 = final_poem(o2, o['oid'], arm, 2) if not ok1 else ''
            v2 = verdicts(o['checks'], p_2) if p_2 else (False, [0]); b2 = base_ok(p_2, MAX_REP)[0] if p_2 else False
            ok2 = ok1 or (v2[0] is True and b2)
            tk = f"{o['oid']}|topic|{arm}"; ch = (o3.get(tk) or {}).get('choice')
            arms[arm] = dict(ok1=ok1, failed1=v1[1] if v1[0] is not True else [], base1=b1, final_ok=ok2, failed2=v2[1] if p_2 and v2[0] is not True else [],
                             topic_ok=(ch == key.get(tk)) if tk in key else None)
        e['arms'] = arms
        e['calib'] = {n: ((o3.get(f"{o['oid']}|topic|{n}") or {}).get('choice') == key.get(f"{o['oid']}|topic|{n}")) for n in ('witness', 'witness_shuffled') if f"{o['oid']}|topic|{n}" in key}
        e['points'] = sum(not arms[a]['final_ok'] for a in ARMS) if e['status'] == 'fair' else 0
        res.append(e)
    W(os.path.join(rd(r), 'score.json'), dict(round=r, orders=res))
    for e in res:
        a = e.get('arms') or {}
        print(e['oid'], e['status'], '|', ' '.join(f"{k}:{'+' if v['ok1'] else '-'}{'+' if v['final_ok'] else '-'}" for k, v in a.items()), '| очки', e.get('points'), '|', e['title'][:40])

if __name__ == '__main__':
    c = sys.argv[1]; r = int(sys.argv[2]); a = sys.argv[3:]
    {'attack': lambda: attack(r), 'accept': lambda: accept(r, a[0]), 'merge_fix': lambda: merge_fix(r, a[0]), 'stage1': lambda: stage1(r),
     'stage2': lambda: stage2(r, a[0]), 'stage3': lambda: stage3(r, a[0], a[1] if len(a) > 1 else None),
     'score': lambda: score(r, a[0], a[1] if len(a) > 1 else None, a[2] if len(a) > 2 else None)}[c]()
