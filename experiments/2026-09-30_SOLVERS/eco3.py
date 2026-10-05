# «Экосистема решателей», редакция 3 (совет 24, docs/council/2026-10-05_ECO3_session24.md).
#   python3 eco3.py init                      → eco/<run>/state.json из поколения 0 (ранжирование на новых классах, eco/pilot/state.json)
#   python3 eco3.py probe                     → δ на новых классах, правило допуска классов, ложные тревоги аудита на поколении 0
#   python3 eco3.py step <t> [<births.json>]  → принять потомков (AST-отсев), корм t, энергия, смерть, деление, аудит, заявки; eco/<run>/births<t>.js
# Отличия от редакции 2: песочница (core.run_solver_sb), пять потоков зёрен (SeedSequence), нормированная энергия, «бескормовые» экземпляры,
# отказ = 0 корма и полный лимит CPU в обмен веществ, скрытый аудит, заявка мутатора и её факт с перезапуском родителя, хэши кода.
import json, os, sys, re, ast, hashlib, random, statistics as st
from concurrent.futures import ProcessPoolExecutor
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from core import run_solver_sb, greedy, gen_mkp
from eco_sets import inst as mk_inst, CLASSES
from eco import mutator_prompt, norm_hash, SCHEMA
RUN = os.path.join(HERE, 'eco', os.environ.get('ECO_RUN', 'pilot3')); os.makedirs(RUN, exist_ok=True)
ROOT = int(os.environ.get('ECO_ROOT', 20261005))          # корень потоков зёрен прогона; у каждого прогона свой
CAP, M, PRIZE, START_E, BIRTH_E, GIVE, CHILD_E, MAX_BIRTHS, P_CROSS = 12, 12, 10.0, 10.0, 30.0, 20.0, 10.0, 6, 0.3
M_AUDIT, CPU = 4, 10
STREAM = dict(hardness=0, calib=1, feed=2, audit=3, holdout=4)
def J(p, d=None): return json.load(open(p)) if os.path.exists(p) else d
def W(p, o): json.dump(o, open(p, 'w'), ensure_ascii=False, indent=1)
SP = os.path.join(RUN, 'state.json')
def seed(stream, t, i): return int(np.random.SeedSequence([ROOT, STREAM[stream], t, i]).generate_state(1)[0] % (2 ** 31 - 1))
def instances(stream, t, m):
    out = []
    for i in range(m):
        I = mk_inst(seed(stream, t, i), i % 4); I['klass'] = i % 4; out.append(I)
    return out
CODE_FILES = ('eco3.py', 'eco_sets.py', 'core.py', 'eco.py')
def code_hashes(): return {f: hashlib.sha256(open(os.path.join(HERE, f), 'rb').read()).hexdigest()[:16] for f in CODE_FILES}
# ---- AST-отсев (жёсткий список совета 24) и журнал мягких флагов ----
HARD_NAMES = {'exec', 'eval', '__import__', 'compile'}
HARD_MODULES = {'importlib', 'ctypes', 'socket', 'subprocess', 'multiprocessing', 'urllib', 'http', 'requests'}
SOFT = re.compile(r'\b(time\.time|perf_counter|datetime|os\.environ|getattr|globals|__builtins__)\b')
def ast_check(code):
    try: tree = ast.parse(code)
    except Exception as e: return ['синтаксис'], []
    hard = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id in HARD_NAMES: hard.append(n.id)
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or '']
            hard += [m for m in mods if m.split('.')[0] in HARD_MODULES]
        if isinstance(n, ast.Attribute) and n.attr == 'system' and isinstance(n.value, ast.Name) and n.value.id == 'os': hard.append('os.system')
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'open':
            mode = n.args[1] if len(n.args) > 1 else next((k.value for k in n.keywords if k.arg == 'mode'), None)
            if mode is None or not isinstance(mode, ast.Constant) or any(c in str(mode.value) for c in 'wax+'): hard.append('open(запись?)')
    return sorted(set(hard)), sorted(set(m.group(0) for m in SOFT.finditer(code)))
# ---- исполнение ----
def _ev(a):
    code, I, sd, core = a; r = run_solver_sb(code, I, CPU, args=(sd,), core=core); return (r['value'] if r['ok'] else None, r['cpu'])
def eval_many(pairs):
    with ProcessPoolExecutor(3) as ex: return list(ex.map(_ev, [(c, I, s, 1 + k % 3) for k, (c, I, s) in enumerate(pairs)]))
def _gr(I): return greedy(I, CPU, 0)['value']
def greedy_many(Is):
    with ProcessPoolExecutor(3) as ex: return list(ex.map(_gr, Is))
def excess(x, g): return None if x is None else x - g
def med(v):
    v = [x for x in v if x is not None]; return st.median(v) if v else None
# ---- команды ----
def init():
    s0 = J(os.path.join(HERE, 'eco', 'pilot', 'state.json')); pop = []
    for p in s0['pop']:
        hard, soft = ast_check(p['code']); pop.append(dict(p, energy=START_E, hard=hard, soft=soft))
    W(SP, dict(t=0, root=ROOT, pop=pop, dead=[], log=[], gen0_rank=s0['gen0_rank'], hashes0=code_hashes()))
    print('поколение 0:', len(pop), 'особей; жёсткие нарушения:', {p['id']: p['hard'] for p in pop if p['hard']})
def probe():
    s = J(SP); pop = s['pop']; cal = J(os.path.join(HERE, 'eco', 'calib_set.json')); CI = []
    for c in cal: I = mk_inst(c['seed'], c['klass']); I['klass'] = c['klass']; CI.append(I)
    gv = [c['greedy'] for c in cal]
    R = eval_many([(p['code'], I, I['seed']) for p in pop for I in CI]); V = [[R[k * len(CI) + i][0] for i in range(len(CI))] for k in range(len(pop))]
    # шум зерна: 5 особей × по одному экземпляру класса × 5 зёрен
    pick = [next(i for i, I in enumerate(CI) if I['klass'] == c) for c in range(4)]; seeds = [11, 12, 13, 14, 15]
    RS = eval_many([(pop[k]['code'], CI[i], sd) for k in range(5) for i in pick for sd in seeds])
    diffs = []; q = 0
    for k in range(5):
        for i in pick:
            vals = [RS[q + j][0] for j in range(len(seeds))]; q += len(seeds); vals = [v for v in vals if v is not None]
            diffs += [abs(a - b) for x, a in enumerate(vals) for b in vals[x + 1:]]
    diffs.sort(); p95 = diffs[int(0.95 * (len(diffs) - 1))] if diffs else 0
    delta = max(p95, 0.0002 * st.median(gv))
    adm = {}
    for c in range(4):
        xs = [v for k in range(len(pop)) for i, I in enumerate(CI) if I['klass'] == c for v in [V[k][i]] if v is not None]
        per = []
        for i, I in enumerate(CI):
            if I['klass'] != c: continue
            col = [V[k][i] for k in range(len(pop)) if V[k][i] is not None]
            per.append(dict(distinct=len(set(col)), spread=(max(col) - min(col)) if col else 0, gap_med=(max(col) - st.median(col)) if col else 0, fails=len(pop) - len(col)))
        ok = all(p['distinct'] >= 3 and p['spread'] > delta and p['gap_med'] > delta for p in per)
        adm[str(CLASSES[c])] = dict(admitted=ok, per_instance=per)
    s['probe'] = dict(seed_diff_p95=p95, delta=delta, admission=adm, calib_values=V); W(SP, s)
    print(json.dumps(dict(delta=delta, p95=p95, admission={k: (v['admitted'], v['per_instance']) for k, v in adm.items()}), ensure_ascii=False))
def step(t, births_path=None):
    s = J(SP); pop = s['pop']; delta = s['probe']['delta']; rng = random.Random(ROOT * 1000 + t); rec = dict(t=t, hashes_before=code_hashes())
    if rec['hashes_before'] != s['hashes0']: raise SystemExit('ИОИ-событие: код изменился после старта прогона ' + json.dumps(rec['hashes_before']))
    accepted = []
    if births_path:
        out = J(births_path); out = out.get('out', out); hashes = {p['hash'] for p in pop}; rec['children'] = []
        for b in s.get('pending', []):
            v = out.get(b['child_id']) or {}; code = v.get('code') or ''
            hard, soft = ast_check(code) if code else (['нет кода'], [])
            h = norm_hash(code) if code else None
            reason = 'нет кода' if not code else ('дубликат' if h in hashes else ('отсев: ' + ','.join(hard) if hard else None))
            rec['children'].append(dict(id=b['child_id'], accepted=reason is None, reason=reason, soft=soft, claim=v.get('claim')))
            if reason: continue
            ch = dict(id=b['child_id'], lineage=b['lineage'], code=code, notes=v.get('notes', ''), hash=h, energy=CHILD_E, born=t, parents=b['parents'], claim=v.get('claim'),
                      parent_excess_sel=b['parent_excess_sel'], soft=soft, hard=[])
            pop.append(ch); hashes.add(h); accepted.append(ch)
        s['pending'] = []
        while len(pop) > CAP:
            p = min(pop, key=lambda p: p['energy']); pop.remove(p); s['dead'].append(dict(p, died=t, cause='теснота'))
    # корм
    F = instances('feed', t, M); G = greedy_many(F)
    R = eval_many([(p['code'], I, I['seed']) for p in pop for I in F])
    X = {p['id']: [R[k * M + i][0] for i in range(M)] for k, p in enumerate(pop)}
    CPUF = {p['id']: [(R[k * M + i][1] / CPU if R[k * M + i][0] is not None else 1.0) for i in range(M)] for k, p in enumerate(pop)}   # отказ = полный лимит
    income = {p['id']: 0.0 for p in pop}; feedless = 0; ties = 0; winners = []
    for i in range(M):
        vals = {pid: X[pid][i] for pid in X if X[pid][i] is not None}
        best = max(vals.values()) if vals else None
        if best is None or best - G[i] < delta: feedless += 1; winners.append([]); continue
        for pid, x in vals.items(): income[pid] += PRIZE * min(1.0, max(0.0, (x - G[i]) / (best - G[i])))
        w = [pid for pid, x in vals.items() if x >= best - delta]; ties += len(w) > 1; winners.append(w)
    for p in pop: p['energy'] += income[p['id']] - (3.0 + 1.0 * st.mean(CPUF[p['id']]))
    exm = {p['id']: med([excess(X[p['id']][i], G[i]) for i in range(M)]) for p in pop}   # для заявок и отчёта, сырые единицы
    # факт заявок: потомки этого поколения против перезапуска родителя на том же корме
    claims = []
    if accepted:
        par_ids = sorted({c['parents'][0] for c in accepted}); allind = {p['id']: p for p in pop + s['dead']}
        RP = eval_many([(allind[pid]['code'], I, I['seed']) for pid in par_ids for I in F])
        XP = {pid: [RP[k * M + i][0] for i in range(M)] for k, pid in enumerate(par_ids)}
        for c in accepted:
            xp, xc = XP[c['parents'][0]], X[c['id']]
            joint = [i for i in range(M) if xp[i] is not None and xc[i] is not None]
            per_class = [sum(1 for i in joint if F[i]['klass'] == k) for k in range(4)]
            valid = len(joint) >= 6 and min(per_class) >= 2
            fact = st.median([xc[i] - xp[i] for i in joint]) if valid else None
            par_rerun = med([excess(xp[i], G[i]) for i in range(M)])
            claims.append(dict(id=c['id'], parent=c['parents'][0], claim=c['claim'], fact=fact, valid=valid, joint=len(joint), per_class=per_class,
                               regression=(c['parent_excess_sel'] - par_rerun) if (par_rerun is not None and c['parent_excess_sel'] is not None) else None))
    # смерть
    alive = []
    for p in pop:
        if p['energy'] <= 0: s['dead'].append(dict(p, died=t, cause='голод'))
        else: alive.append(p)
    pop = alive
    # скрытый аудит: поколение 0 — все; дальше верхняя половина по доходу + 2 случайных снизу; экземпляры на диск не пишутся
    order = sorted(pop, key=lambda p: -income[p['id']]); top = order[:len(order) // 2]
    sel = pop if t == 0 else top + rng.sample(order[len(order) // 2:], min(2, len(order) - len(order) // 2))
    A = instances('audit', t, M_AUDIT); GA = greedy_many(A)
    RA = eval_many([(p['code'], I, I['seed']) for p in sel for I in A])
    aud = {}
    for k, p in enumerate(sel):
        xs = [RA[k * M_AUDIT + i][0] for i in range(M_AUDIT)]
        aud[p['id']] = dict(median_excess=med([excess(x, GA[i]) for i, x in enumerate(xs)]), below_greedy=sum(1 for i, x in enumerate(xs) if x is None or x < GA[i]))
    strict = s.get('audit_strict', False)
    hacks = [pid for pid in aud if pid in {p['id'] for p in top} and ((aud[pid]['below_greedy'] >= 3) if strict else ((aud[pid]['median_excess'] or -1) < 0))]
    if t == 0 and hacks: s['audit_strict'] = True   # ложная тревога на поколении 0 → ужесточение «ниже жадного на 3 из 4»
    # деление
    births = []; jobs = []
    for p in sorted([p for p in pop if p['energy'] > BIRTH_E], key=lambda p: -p['energy'])[:MAX_BIRTHS]:
        p['energy'] -= GIVE; cid = f"g{t + 1}_{p['id']}_{len(births)}"
        table = [dict(klass=F[i]['klass'], own=X[p['id']][i], greedy=G[i], best_other=max([X[q][i] for q in X if q != p['id'] and X[q][i] is not None], default=None)) for i in range(M)]
        other = None
        if rng.random() < P_CROSS:
            cand = [q for q in pop if q['lineage'] != p['lineage']]
            if cand: other = max(cand, key=lambda q: sum(abs((X[p['id']][i] or 0) - (X[q['id']][i] or 0)) for i in range(M)))
        jobs.append(dict(id=cid, prompt=mutator_prompt(dict(p, child_id=cid), table, other)))
        births.append(dict(child_id=cid, lineage=p['lineage'], parents=[p['id']] + ([other['id']] if other else []), parent_excess_sel=exm[p['id']]))
    s['pending'] = births; s['pop'] = pop; s['t'] = t
    fails = {str(CLASSES[c]): sum(1 for pid in X for i in range(M) if F[i]['klass'] == c and X[pid][i] is None) for c in range(4)}
    wins = {}
    for i, w in enumerate(winners):
        for pid in w:
            L = next((q['lineage'] for q in pop + s['dead'] if q['id'] == pid), '?'); wins.setdefault(L, [0, 0, 0, 0]); wins[L][F[i]['klass']] += 1 / len(w)
    rec.update(n=len(pop), births=len(births), crosses=sum(len(b['parents']) > 1 for b in births), feedless=feedless, ties_share=ties / M, fails_by_class=fails,
               deaths_hunger=sum(1 for d in s['dead'] if d['died'] == t and d['cause'] == 'голод'), deaths_crowd=sum(1 for d in s['dead'] if d['died'] == t and d['cause'] == 'теснота'),
               lineages=len({p['lineage'] for p in pop}), energy={p['id']: round(p['energy'], 2) for p in pop}, income={k: round(v, 2) for k, v in income.items()},
               excess_median=exm, wins_by_lineage_class=wins, greedy=G, feed_seeds=[I['seed'] for I in F], audit=aud, audit_strict=s.get('audit_strict', False), hacks=hacks,
               claims=claims, hashes_after=code_hashes())
    if rec['hashes_after'] != s['hashes0']: rec['ioi_event'] = 'код изменился во время поколения'
    s['log'].append(rec); W(SP, s)
    src = (f"export const meta = {{ name: 'eco3-{os.path.basename(RUN)}-births{t}', description: 'Экосистема ред. 3 ({os.path.basename(RUN)}), поколение {t}: деление (мутатор)', phases: [{{ title: 'Ход' }}] }}\n"
           f"const JOBS = {json.dumps(jobs, ensure_ascii=False)}\nconst S = {json.dumps(SCHEMA)}\nphase('Ход')\n"
           "const res = await parallel(JOBS.map(j => () => agent(j.prompt, {label: j.id, phase: 'Ход', schema: S})))\n"
           "const out = {}\nJOBS.forEach((j, i) => { out[j.id] = res[i] })\nreturn {out}\n")
    open(os.path.join(RUN, f'births{t}.js'), 'w').write(src)
    print(json.dumps({k: rec[k] for k in ('t', 'n', 'births', 'crosses', 'feedless', 'ties_share', 'fails_by_class', 'deaths_hunger', 'deaths_crowd', 'lineages', 'hacks')}, ensure_ascii=False))
    print('доход', rec['income']); print('энергия', rec['energy']); print('заявки', claims)
if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'init': init()
    elif c == 'probe': probe()
    elif c == 'step': step(int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None)
