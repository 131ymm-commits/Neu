# LEVEL-05, ветвь организаций: план и смета, сборка сценариев, заморозка макромодели, анализ, сухой прогон на моках.
#   python3 org.py plan                                  → смета вызовов по ячейкам (run/budget.json)
#   python3 org.py build-calib <tag> <calib_tag>         → run/<tag>.js: 56 вызовов калибровки 2 (tasks.py calib2)
#   python3 org.py freeze <frozen_tag> <calib2_out.json> → run/macro_frozen_<frozen_tag>.json (параметры, формула, интервалы) + sha256
#   python3 org.py build <tag>                           → run/<tag>.js: все ячейки плана на задачах tasks/<tag>.json
#   python3 org.py analyze <tag> <out.json> <frozen_tag> → run/<tag>_analysis.json, печать таблиц и сертификата
#   python3 org.py mockchain                             → вся цепочка на моках (tasks → калибровка → заморозка → прогон → анализ)
# Ячейки (генотип, N): a — дерево без защиты (листья = первичные вызовы b, «копия A»), b — дерево + проверка листа другим путём
# (первичный генотип), c — цепочка, s — одиночка одним вызовом, e — одиночка с равным бюджетом (самопродолжение).
import json, os, sys, math, random, hashlib, subprocess, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); SECRET = '/root/level5_secret'
sys.path.insert(0, HERE)
from tasks import tree_spans, LEAF
NS = (5, 10, 20)
Z = 1.959963984540054

# ---------------- план ----------------
def plan_jobs(task_ids, n_self=8, a20_seeds=None):
    """Задания на один прогон. a20_seeds: сколько зёрен ячейки «без защиты» идут деревом N = 20 (остальные — N = 10)."""
    a20 = len(task_ids) if a20_seeds is None else a20_seeds
    J = []
    for i, t in enumerate(task_ids):
        J.append(dict(id=f'b20-{t}', kind='tree', task=t, N=20, check='tr'))
        J.append(dict(id=f'a{20 if i < a20 else 10}-{t}', kind='tree', task=t, N=20 if i < a20 else 10, check='none', share=f'b20-{t}'))
        J.append(dict(id=f'c10-{t}', kind='chain', task=t, N=10))
        for N in NS: J.append(dict(id=f's{N}-{t}', kind='single', task=t, N=N))
        if i < n_self: J.append(dict(id=f'e10-{t}', kind='self', task=t, N=10, match=f'b20-{t}', K=42))
    return J

def calls_b(N, mism):
    """Вызовы дерева b на N листьях при числе расхождений P≠TR mism: 2 на лист + 3 на расхождение + N−1 сборок."""
    return 2 * N + 3 * mism + (N - 1)

def budget(eps_leaf=0.25, n_seeds=10, n_self=8, target=1600, calib=56, sims=20000):
    pm = 1 - (1 - eps_leaf) ** 2          # вероятность расхождения P и TR при независимости (ρ = 0 — худший случай для сметы)
    def table(a20):
        rows = []
        rows.append(('калибровка 2 (новые зёрна): 20 сборок + 12×(P, TR) M=10 + 12 M=5', 'calib', 1, calib, calib, calib, calib))
        rows.append(('b: дерево + проверка другим путём, N=20 (N=5,10 — поддеревья)', 'b20', n_seeds, calls_b(20, 0), calls_b(20, 20 * pm), None, calls_b(20, 20)))
        rows.append(('a: дерево без защиты N=20 (листья общие с b)', 'a20', a20, 19, 19, 19, 19))
        if a20 < n_seeds: rows.append(('a: дерево без защиты N=10 (листья общие с b)', 'a10', n_seeds - a20, 9, 9, 9, 9))
        rows.append(('c: цепочка N=10', 'c10', n_seeds, 10, 10, 10, 10))
        for N in NS: rows.append((f's: одиночка одним вызовом N={N}', f's{N}', n_seeds, 1, 1, 1, 1))
        rows.append(('e: равный бюджет N=10 (K = вызовы b на поддереве N=10)', 'e10', n_self, calls_b(10, 0), calls_b(10, 10 * pm), None, calls_b(10, 10)))
        return rows
    rng = random.Random(0)
    def sim_total(a20):
        tot = calib + a20 * 19 + (n_seeds - a20) * 9 + n_seeds * 10 + 3 * n_seeds
        for i in range(n_seeds):
            m1 = sum(rng.random() < pm for _ in range(10)); m2 = sum(rng.random() < pm for _ in range(10))
            tot += calls_b(20, m1 + m2) + (calls_b(10, m1) if i < n_self else 0)
        return tot
    for a20 in [n_seeds] + list(range(n_seeds - 1, 5, -1)):
        rows = table(a20)
        exp = sum(r[2] * r[4] for r in rows)
        if exp <= target or a20 == 6: break
    sims_t = sorted(sim_total(a20) for _ in range(sims))
    res = dict(eps_leaf=eps_leaf, p_mismatch=round(pm, 4), a20_seeds=a20, n_seeds=n_seeds, n_self=n_self,
               rows=[dict(cell=r[1], what=r[0], seeds=r[2], per_seed_min=r[3], per_seed_exp=round(r[4], 2), per_seed_max=r[6],
                          total_min=r[2] * r[3], total_exp=round(r[2] * r[4], 1), total_max=r[2] * r[6]) for r in rows])
    res['total'] = dict(min=sum(r['total_min'] for r in res['rows']), exp=round(sum(r['total_exp'] for r in res['rows']), 1),
                        p95=sims_t[int(0.95 * sims)], p99=sims_t[int(0.99 * sims)], max=sum(r['total_max'] for r in res['rows']))
    return res

def print_budget(b):
    print(f"Смета (ε листа = {b['eps_leaf']}, P(расхождение P≠TR) = {b['p_mismatch']}; зёрен {b['n_seeds']}, равный бюджет на {b['n_self']}; a N=20 на {b['a20_seeds']} зёрнах)")
    print(f"{'ячейка':6} {'зёрен':>5} {'мин/зерно':>9} {'ожид/зерно':>10} {'макс/зерно':>10} {'итого мин':>9} {'итого ожид':>10} {'итого макс':>10}  что")
    for r in b['rows']:
        print(f"{r['cell']:6} {r['seeds']:>5} {r['per_seed_min']:>9} {r['per_seed_exp']:>10} {r['per_seed_max']:>10} {r['total_min']:>9} {r['total_exp']:>10} {r['total_max']:>10}  {r['what']}")
    t = b['total']; print(f"ИТОГО: мин {t['min']}, ожидаемое {t['exp']}, 95-й перцентиль {t['p95']}, 99-й {t['p99']}, макс {t['max']}")

# ---------------- сборка сценариев ----------------
def write_script(tag, tasks, jobs):
    src = open(f'{HERE}/org_step.js').read()
    assert 'const TASKS = null' in src and 'const JOBS = null' in src
    src = src.replace('const TASKS = null', 'const TASKS = ' + json.dumps(tasks, separators=(',', ':')), 1).replace('const JOBS = null', 'const JOBS = ' + json.dumps(jobs, ensure_ascii=False, separators=(',', ':')), 1)
    os.makedirs(f'{HERE}/run', exist_ok=True); open(f'{HERE}/run/{tag}.js', 'w').write(src)
    print(f'run/{tag}.js: заданий {len(jobs)}, sha256 {hashlib.sha256(src.encode()).hexdigest()[:16]}')

def calib_jobs(ctasks):
    """56 вызовов: сборка A·B (20), лист M=10 путём P и путём TR (12 × 2), половина M=5 (12)."""
    J = []
    for t in ctasks:
        if t['kind'] == 'asm': J.append(dict(id=f'asm-{t["id"]}', kind='prod', task=t['id'], **{'from': 0, 'to': 2}, variant='lr'))
        elif t['kind'] == 'm10':
            J.append(dict(id=f'p10-{t["id"]}', kind='prod', task=t['id'], **{'from': 0, 'to': 10}, variant='lr'))
            J.append(dict(id=f'tr10-{t["id"]}', kind='prod', task=t['id'], **{'from': 0, 'to': 10}, variant='tr'))
        elif t['kind'] == 'm5': J.append(dict(id=f'p5-{t["id"]}', kind='prod', task=t['id'], **{'from': 0, 'to': 5}, variant='lr'))
    return J
def build_calib(tag, ctag):
    ct = json.load(open(f'{HERE}/tasks/{ctag}.json'))
    jobs = calib_jobs(ct)
    json.dump(dict(calib_tag=ctag, calls=len(jobs)), open(f'{HERE}/run/{tag}_meta.json', 'w'))
    write_script(tag, {t['id']: dict(p=t['p'], matrices=t['matrices']) for t in ct}, jobs)

def build(tag, n_self=8, a20_seeds=None):
    tasks = json.load(open(f'{HERE}/tasks/{tag}.json'))
    b = budget(n_seeds=len(tasks), n_self=n_self)
    a20 = b['a20_seeds'] if a20_seeds is None else a20_seeds
    jobs = plan_jobs([t['id'] for t in tasks], n_self=n_self, a20_seeds=a20)
    json.dump(dict(budget=b, jobs=jobs), open(f'{HERE}/run/{tag}_plan.json', 'w'), ensure_ascii=False, indent=1)
    print_budget(b)
    write_script(tag, {t['id']: dict(p=t['p'], matrices=t['matrices']) for t in tasks}, jobs)

# ---------------- макромодель ----------------
def key(m): return ','.join(str(x) for x in (m[0][0], m[0][1], m[1][0], m[1][1]))
MODEL_TEXT = ('P_org = Π по узлам [1 − ε_узла·(1−d)^v]; ε_leaf, ε_asm из калибровки; v = 1 у листьев генотипа b, 0 иначе. '
              'Для b 1 − ε_leaf·(1−d) = P_leaf_b = (1−εL)(1−εT) + (1−εL)·εT·(1−εH) + εL·(1−ρ)·(1−εH), εH = 1 − (1−ε5)²(1−εA), '
              'ρ = P(TR даёт тот же неверный ответ | P неверен). a: (1−εL)^N (1−εA)^(N−1); b: P_leaf_b^N (1−εA)^(N−1); '
              'c: (1−εL)^N (звено ≈ лист). Интервал: параметры ~ Beta(k+½, n−k+½) (Джеффрис), наблюдаемая доля ~ Binom(n_зёрен, P)/n; 5–95 %.')
def model_P(N, cell, eL, e5, eA, eT, rho):
    if cell == 'a': return (1 - eL) ** N * (1 - eA) ** (N - 1)
    if cell == 'c': return (1 - eL) ** N
    eH = 1 - (1 - e5) ** 2 * (1 - eA)
    pl = (1 - eL) * (1 - eT) + (1 - eL) * eT * (1 - eH) + eL * (1 - rho) * (1 - eH)
    return pl ** N * (1 - eA) ** (N - 1)

def calib_counts(calib2_out):
    """Счётчики (ошибок, n) — только из калибровки 2 (новые зёрна): εL (путь P, M=10), εT (путь TR, M=10, ключ уже переставлен
    обратно в сценарии), ρ = P(TR даёт тот же неверный ответ | P неверен), ε5 (M=5), εA (сборка). Сбой формата = ошибка.
    Первая калибровка (C*-70x) в заморозку не входит — только для справки (calib_analysis.json)."""
    O = json.load(open(calib2_out)); outs = O['out']
    meta = json.load(open(calib2_out.replace('_out.json', '_meta.json')))
    truth = json.load(open(f'{SECRET}/{meta["calib_tag"]}.json'))['tasks']
    bad = lambda v: v is None or v.get('key') is None or v['key'] != key(truth[v['task']]['truth'])
    grp = lambda pre: [v for j, v in outs.items() if j.startswith(pre + '-')]
    cnt = {'eL': grp('p10'), 'eT': grp('tr10'), 'e5': grp('p5'), 'eA': grp('asm')}
    cnt = {k: [sum(bad(v) for v in vs), len(vs)] for k, vs in cnt.items()}
    same = nwrong = 0
    for j, v in outs.items():
        if j.startswith('p10-') and bad(v):
            nwrong += 1; w = outs.get('tr10-' + j[4:])
            if v.get('key') is not None and w and w.get('key') == v['key']: same += 1
    cnt['rho'] = [same, nwrong]
    return cnt

def freeze(ftag, calib2_out, plan_n=None, draws=20000):
    cnt = calib_counts(calib2_out)
    mle = {k: (a / n if n else 0.0) for k, (a, n) in cnt.items()}
    rng = random.Random(12345)
    beta = lambda k, n: rng.betavariate(k + 0.5, n - k + 0.5)
    plan_n = plan_n or {'a': {5: 10, 10: 10, 20: 10}, 'b': {5: 10, 10: 10, 20: 10}, 'c': {10: 10}}
    pred = {}
    for cell, Ns in plan_n.items():
        for N, n in Ns.items():
            Ps, obs = [], []
            for _ in range(draws):
                th = {k: beta(*cnt[k]) for k in cnt}
                P = model_P(N, cell, th['eL'], th['e5'], th['eA'], th['eT'], th['rho']); Ps.append(P)
                obs.append(sum(rng.random() < P for _ in range(n)) / n)
            Ps.sort(); obs.sort()
            pred[f'{cell}{N}'] = dict(n_seeds=n, plugin=round(model_P(N, cell, mle['eL'], mle['e5'], mle['eA'], mle['eT'], mle['rho']), 4),
                                      mean=round(st.mean(Ps), 4), P_90=[round(Ps[int(0.05 * draws)], 4), round(Ps[int(0.95 * draws) - 1], 4)],
                                      obs_90=[obs[int(0.05 * draws)], obs[int(0.95 * draws) - 1]])
    eL, eA = mle['eL'], mle['eA']
    d_eff = 1 - (1 - model_P(1, 'b', eL, mle['e5'], 0.0, mle['eT'], mle['rho'])) / eL if eL else None
    fr = dict(model=MODEL_TEXT, counts=cnt, mle={k: round(v, 4) for k, v in mle.items()}, d_eff_plugin=round(d_eff, 4) if d_eff is not None else None,
              prior='Jeffreys Beta(½,½)', draws=draws, rng_seed=12345, predictions=pred,
              org_py_sha256=hashlib.sha256(open(__file__, 'rb').read()).hexdigest())
    body = json.dumps(fr, ensure_ascii=False, sort_keys=True)
    fr['frozen_sha256'] = hashlib.sha256(body.encode()).hexdigest()
    path = f'{HERE}/run/macro_frozen_{ftag}.json'
    if os.path.exists(path) and ftag != 'orgmock': raise SystemExit(f'{path} уже заморожен — не перезаписываю')
    json.dump(fr, open(path, 'w'), ensure_ascii=False, indent=1)
    print('калибровка (ошибок, n):', cnt, '\nплагин-оценки:', fr['mle'], ' d_eff =', fr['d_eff_plugin'])
    for c, v in pred.items(): print(f"  {c}: плагин {v['plugin']}, E[P] {v['mean']}, 90 % P {v['P_90']}, 90 % наблюдаемой доли при n={v['n_seeds']}: {v['obs_90']}")
    print('заморожено →', path, 'sha256', fr['frozen_sha256'])
    return fr

def check_frozen(fr):
    body = {k: v for k, v in fr.items() if k != 'frozen_sha256'}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest() == fr['frozen_sha256']

# ---------------- статистика ----------------
def wilson(x, n):
    if n == 0: return (0.0, 1.0)
    c = (x + Z * Z / 2) / (n + Z * Z); h = Z * math.sqrt(x * (n - x) / n + Z * Z / 4) / (n + Z * Z)
    return (max(0.0, c - h), min(1.0, c + h))
def newcombe_paired(pairs):
    """Ньюкомб (1998), метод 10: 95 % ДИ разности долей для парных бинарных данных (x = организация, y = контроль)."""
    n = len(pairs)
    if n == 0: return (None, None)
    a = sum(1 for x, y in pairs if x and y); b = sum(1 for x, y in pairs if x and not y)
    c = sum(1 for x, y in pairs if not x and y); d = n - a - b - c
    p1, p2 = (a + b) / n, (a + c) / n
    l1, u1 = wilson(a + b, n); l2, u2 = wilson(a + c, n)
    den = (a + b) * (c + d) * (a + c) * (b + d)
    if den == 0: phi = 0.0
    else:
        num = a * d - b * c
        num = max(num - n / 2, 0) if num > 0 else num
        phi = num / math.sqrt(den)
    D = p1 - p2
    L = D - math.sqrt(max(0.0, (p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2))
    U = D + math.sqrt(max(0.0, (u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2))
    return (round(L, 4), round(U, 4))
def boot_paired(pairs, B=10000, seed=0):
    if not pairs: return (None, None)
    r = random.Random(seed); n = len(pairs); diffs = [x - y for x, y in pairs]; ms = []
    for _ in range(B): ms.append(sum(diffs[r.randrange(n)] for _ in range(n)) / n)
    ms.sort(); return (round(ms[int(0.025 * B)], 4), round(ms[int(0.975 * B) - 1], 4))
def paired(A, C):
    """A, C: {seed: 0/1}. Парная разность по общим зёрнам; нижняя граница = min(бутстреп 2,5 %, Ньюкомб)."""
    common = sorted(set(A) & set(C)); pairs = [(A[s], C[s]) for s in common]
    if not pairs: return dict(n=0)
    bl, bu = boot_paired(pairs); nl, nu = newcombe_paired(pairs)
    return dict(n=len(pairs), diff=round(st.mean(x - y for x, y in pairs), 4), boot95=[bl, bu], newcombe95=[nl, nu], lower=min(bl, nl))

# ---------------- анализ ----------------
def analyze(tag, path, ftag):
    fr = json.load(open(f'{HERE}/run/macro_frozen_{ftag}.json'))
    if not check_frozen(fr): raise SystemExit('макромодель изменена после заморозки (sha256 не совпадает)')
    sec = json.load(open(f'{SECRET}/{tag}.json'))['tasks']; O = json.load(open(path)); out, recs = O['out'], O.get('records', [])
    eps_m = 1 - (1 - fr['mle']['eL']) ** (1 / LEAF)                  # ε на одно умножение матриц (для «трудности M·ε»)
    cells = {}                                                        # (cell, N) -> {seed: status}
    def put(cell, N, t, status): cells.setdefault((cell, N), {})[t] = status
    def st_of(k, fmt, truth, refused=False):
        if refused: return 'refused'
        if k is None: return 'fmt' if fmt not in (None, 'child') else ('child' if fmt == 'child' else 'fmt')
        return 'ok' if k == key(truth) else 'wrong'
    secondary = {}
    for jid, o in out.items():
        t = o['task']; S = sec[t]
        if 'error' in o: print('ОШИБКА задания', jid, o['error']); continue
        kind = o['kind']
        if kind == 'tree':
            cell = jid[0]
            for N in NS:
                nd = o['nodes'].get(f'0:{N}')
                if nd is not None: put(cell, N, t, st_of(nd['key'], nd['fmt'], S['spans'][f'0:{N}']))
            for sp in ('5:10', '10:15', '15:20', '10:20'):
                nd = o['nodes'].get(sp)
                if nd is not None:
                    lo, hi = map(int, sp.split(':')); secondary.setdefault((cell, hi - lo), []).append(st_of(nd['key'], nd['fmt'], S['spans'][sp]) == 'ok')
        elif kind == 'chain': put('c', 10, t, st_of(o['key'], o['fmt'], S['spans']['0:10']))
        elif kind == 'single': N = int(jid[1:jid.index('-')]); put('s', N, t, st_of(o['key'], o['fmt'], S['spans'][f'0:{N}'], o.get('refused')))
        elif kind == 'self': put('e', 10, t, st_of(o['key'], o['fmt'], S['prefix'][99]))
    calls = {}
    for jid, o in out.items():
        if o.get('kind') in ('tree', 'chain', 'single', 'self'): calls.setdefault(jid.split('-')[0], []).append(o.get('calls', 0))
    # таблица по ячейкам
    table = {}
    for (cell, N), d in sorted(cells.items(), key=lambda x: ('bacse'.index(x[0][0]), x[0][1])):
        n = len(d); ok = sum(v == 'ok' for v in d.values())
        row = dict(n=n, acc=round(ok / n, 4) if n else None, ok=ok, wrong=sum(v == 'wrong' for v in d.values()),
                   fmt=sum(v in ('fmt', 'child') for v in d.values()), refused=sum(v == 'refused' for v in d.values()),
                   M=10 * N, M_eps=round(10 * N * eps_m, 2), wilson95=[round(x, 3) for x in wilson(ok, n)])
        row['fail_nonanswer_share'] = round((row['fmt'] + row['refused']) / n, 4) if n else None
        table[f'{cell}{N}'] = row
    for jid, o in out.items():                                       # вызовы поддерева N в деревьях (для b5, b10, a5, a10)
        if o.get('kind') == 'tree':
            for N in NS:
                sub = [v.get('calls', 0) for sp, v in o['nodes'].items() if int(sp.split(':')[1]) <= N]
                if f'0:{N}' in o['nodes'] and f'{jid[0]}{N}' != jid.split('-')[0]: calls.setdefault(f'{jid[0]}{N}', []).append(sum(sub))
    for k, v in calls.items(): (table.get(k) or {}).update(calls_total=sum(v), calls_per_seed=round(st.mean(v), 2))
    seeds = sorted({t for d in cells.values() for t in d}, key=lambda s: (s[0], int(s[1:])))
    per_seed = {t: {f'{c}{N}': (1 if d.get(t) == 'ok' else 0) if t in d else None for (c, N), d in cells.items()} for t in seeds}
    acc01 = {f'{c}{N}': {t: int(v == 'ok') for t, v in d.items()} for (c, N), d in cells.items()}
    # узлы: ε листа, TR, половин, сборки; ρ; пути решения
    diag = node_diag(out, recs, sec)
    # сертификат
    cert = {}
    for N in NS:
        if f'b{N}' in acc01 and f's{N}' in acc01: cert[f'b{N}-s{N}'] = paired(acc01[f'b{N}'], acc01[f's{N}'])
        if f'a{N}' in acc01 and f's{N}' in acc01: cert[f'a{N}-s{N}'] = paired(acc01[f'a{N}'], acc01[f's{N}'])
    if 'b10' in acc01 and 'e10' in acc01: cert['b10-e10'] = paired(acc01['b10'], acc01['e10'])
    if 'b10' in acc01 and 'c10' in acc01: cert['b10-c10'] = paired(acc01['b10'], acc01['c10'])
    macro = {}
    for c, pv in fr['predictions'].items():
        if c in table:
            lo, hi = pv['obs_90']; macro[c] = dict(observed=table[c]['acc'], n=table[c]['n'], pred_plugin=pv['plugin'], pred_obs_90=[lo, hi], inside=lo <= table[c]['acc'] <= hi)
    single_ok = {N: (table.get(f's{N}', {}).get('acc') is not None and table[f's{N}']['acc'] <= 0.1 and table[f's{N}']['fail_nonanswer_share'] <= 0.3) for N in NS}
    g = lambda k: (cert.get(k) or {}).get('lower')
    C = dict(
        c1_b20_minus_single_lower_gt_0_3=(g('b20-s20') is not None and g('b20-s20') > 0.3),
        c2_council_b10_minus_equal_lower_gt_0=(g('b10-e10') is not None and g('b10-e10') > 0),
        c2_skeptic_b10_minus_equal_lower_gt_0_2=(g('b10-e10') is not None and g('b10-e10') > 0.2),
        veto_equal_budget_ge_0_8=(table.get('e10', {}).get('acc') or 0) >= 0.8,
        c4_single_le_0_1_and_nonanswer_le_0_3={N: single_ok[N] for N in NS},
        c5_macro_inside_90={c: m['inside'] for c, m in macro.items() if c.startswith('b')})
    base = C['c1_b20_minus_single_lower_gt_0_3'] and not C['veto_equal_budget_ge_0_8'] and C['c4_single_le_0_1_and_nonanswer_le_0_3'][20] and all(C['c5_macro_inside_90'].values())
    C['LEVEL_council'] = bool(base and C['c2_council_b10_minus_equal_lower_gt_0'])
    C['LEVEL_skeptic_strict'] = bool(base and C['c2_skeptic_b10_minus_equal_lower_gt_0_2'])
    C['note'] = 'N = 20 против равного бюджета не сертифицируется (равный бюджет ставится только при N = 10). Нижняя граница = min(бутстреп по зёрнам 2,5 %, Ньюкомб 95 %).'
    res = dict(tag=tag, frozen_sha256=fr['frozen_sha256'], eps_per_matrix=round(eps_m, 4), cells=table, per_seed=per_seed,
               secondary_subtrees={f'{c}{N}': dict(n=len(v), acc=round(st.mean(v), 4)) for (c, N), v in secondary.items()},
               nodes=diag, paired=cert, macro=macro, certificate=C, self_trace=self_diag(out, sec))
    json.dump(res, open(f'{HERE}/run/{tag}_analysis.json', 'w'), ensure_ascii=False, indent=1)
    report(res); return res

def node_diag(out, recs, sec):
    """Ошибки по ролям вызовов. err — безусловная доля неверных; err_cond — при верных входах (для сборок A/HC и звеньев цепочки),
    это и есть ε узла макромодели. Ключ TR переводится обратно (транспонирование) до сравнения. ρ = доля TR, совпавших с неверным P."""
    def back(k): 
        if k is None: return None
        a, b, c, d = k.split(','); return ','.join((a, c, b, d))
    ok_of = {}                                                        # (job, role, node) -> верен ли вызов
    rows = []
    for r in recs:
        o = out.get(r['job'])
        if not o or o.get('kind') not in ('tree', 'chain'): continue
        S = sec[o['task']]; role = r['role']; k = back(r['key']) if role == 'TR' else r['key']; cond = True
        if o['kind'] == 'chain':
            truth = S['prefix'][10 * (r['lo'] + 1) - 1]; role = 'link'
            if r['lo'] > 0: cond = ok_of.get((r['job'], 'link', r['lo'] - 1), False)
        elif role in ('P', 'TR'): truth = S['leaves'][r['lo']]
        elif role in ('H1', 'H2'): truth = S['halves'][r['lo']][0 if role == 'H1' else 1]
        elif role == 'HC': truth = S['leaves'][r['lo']]
        elif role == 'A': truth = S['spans'][f"{r['lo']}:{r['hi']}"]
        else: continue
        ok = k == key(truth); ok_of[(r['job'], role, r['lo'] if role in ('link',) else r['node'])] = ok
        rows.append(dict(role=role, ok=ok, fmt=r['fmt'] is not None, key=k, job=r['job'], node=r['node'], lo=r['lo'], hi=r.get('hi'), cond=cond))
    # условие «входы верны»: для HC — H1 и H2 верны; для A — оба ребёнка узла верны (по сохранённым ключам узлов задания)
    for x in rows:
        if x['role'] == 'HC': x['cond'] = ok_of.get((x['job'], 'H1', x['node']), False) and ok_of.get((x['job'], 'H2', x['node']), False)
        if x['role'] == 'A':
            o = out[x['job']]; S = sec[o['task']]; lo, hi = x['lo'], x['hi']; m = lo + (hi - lo) // 2
            x['cond'] = all(o['nodes'].get(f'{a}:{b}', {}).get('key') == key(S['spans'][f'{a}:{b}']) for a, b in ((lo, m), (m, hi)))
    by = {}
    for x in rows: by.setdefault(x['role'], []).append(x)
    D = {}
    for role, v in by.items():
        c = [x for x in v if x['cond']]
        D[role] = dict(n=len(v), err=round(1 - st.mean(x['ok'] for x in v), 4), n_cond=len(c), err_cond=round(1 - st.mean(x['ok'] for x in c), 4) if c else None, fmt=sum(x['fmt'] for x in v))
    P = {(x['job'], x['node']): x for x in by.get('P', [])}; TR = {(x['job'], x['node']): x for x in by.get('TR', [])}
    wrongP = [k for k, x in P.items() if not x['ok'] and x['key'] is not None and k in TR]
    D['rho_TR_equals_wrong_P'] = dict(n_wrong_P=len(wrongP), same=sum(TR[k]['key'] == P[k]['key'] for k in wrongP))
    D['both_wrong_P_TR'] = sum(1 for k in wrongP if not TR[k]['ok'])
    paths, false_accept = {}, 0
    for o in out.values():
        if o.get('kind') == 'tree':
            S = sec[o['task']]
            for sp, nd in o['nodes'].items():
                if nd.get('path'):
                    paths[nd['path']] = paths.get(nd['path'], 0) + 1
                    lo = int(sp.split(':')[0])
                    if nd['key'] != key(S['leaves'][lo]): paths[nd['path'] + ':wrong'] = paths.get(nd['path'] + ':wrong', 0) + 1
    D['leaf_paths'] = paths
    return D

def self_diag(out, sec):
    """Одиночка с равным бюджетом: точность контрольных точек по номеру обращения и по позиции k (наклон ε по контексту)."""
    byj, byk, K, used = {}, {}, [], []
    for o in out.values():
        if o.get('kind') != 'self' or 'error' in o: continue
        S = sec[o['task']]; K.append(o['K']); used.append(o['calls'])
        for tr in o['trace']:
            for c in tr['checkpoints']:
                if not isinstance(c.get('k'), int) or not (1 <= c['k'] <= 100): continue
                ok = c.get('key') == key(S['prefix'][c['k'] - 1])
                byj.setdefault(tr['j'], []).append(ok); byk.setdefault((c['k'] - 1) // 10, []).append(ok)
    return dict(K=K, calls_used=used, acc_by_call={j: round(st.mean(v), 3) for j, v in sorted(byj.items())},
                acc_by_k_decile={f'{10 * d + 1}-{10 * d + 10}': round(st.mean(v), 3) for d, v in sorted(byk.items())})

def report(res):
    print(f"\n== LEVEL-05 организации: {res['tag']} (макромодель sha256 {res['frozen_sha256'][:16]}; ε на матрицу {res['eps_per_matrix']}) ==")
    print(f"{'ячейка':7} {'n':>3} {'T':>6} {'верно':>5} {'неверно':>7} {'формат':>6} {'отказ':>5} {'M':>4} {'M·ε':>5} {'вызовов/зерно':>13}  Уилсон 95 %")
    for c, r in res['cells'].items():
        print(f"{c:7} {r['n']:>3} {r['acc']:>6} {r['ok']:>5} {r['wrong']:>7} {r['fmt']:>6} {r['refused']:>5} {r['M']:>4} {r['M_eps']:>5} {str(r.get('calls_per_seed', '')):>13}  {r['wilson95']}")
    print('поддеревья (вторичное):', res['secondary_subtrees'])
    print('по зёрнам:'); cols = list(res['cells'])
    print('   ' + ' '.join(f'{c:>4}' for c in cols))
    for s, d in res['per_seed'].items(): print(f"{s:>3} " + ' '.join(f"{('·' if d.get(c) is None else d[c]):>4}" for c in cols))
    print('узлы:', json.dumps(res['nodes'], ensure_ascii=False))
    print('равный бюджет:', json.dumps(res['self_trace'], ensure_ascii=False))
    print('парные разности (нижняя граница = min(бутстреп, Ньюкомб)):')
    for k, v in res['paired'].items(): print(f'  {k}: {v}')
    print('макромодель (замороженная):')
    for k, v in res['macro'].items(): print(f'  {k}: {v}')
    C = res['certificate']
    print('СЕРТИФИКАТ (рядом — критерий совета и критерий Скептика):')
    print(f"  организация b − одиночка одним вызовом, N=20: нижняя граница {res['paired'].get('b20-s20', {}).get('lower')} > 0,3 → {C['c1_b20_minus_single_lower_gt_0_3']}")
    lb = res['paired'].get('b10-e10', {}).get('lower')
    print(f"  организация b − равный бюджет, N=10: нижняя граница {lb}   совет (> 0): {C['c2_council_b10_minus_equal_lower_gt_0']}   | Скептик (> 0,2): {C['c2_skeptic_b10_minus_equal_lower_gt_0_2']}")
    print(f"  вето: равный бюджет ≥ 0,8 → {C['veto_equal_budget_ge_0_8']};  одиночка ≤ 0,1 при (формат + отказы) ≤ 0,3: {C['c4_single_le_0_1_and_nonanswer_le_0_3']};  макромодель в 90 %: {C['c5_macro_inside_90']}")
    print(f"  УРОВЕНЬ по совету: {C['LEVEL_council']}   | по Скептику (строго): {C['LEVEL_skeptic_strict']}")
    print('  ' + C['note'])

# ---------------- моки ----------------
def sh(*a):
    print('$', ' '.join(a)); r = subprocess.run(a, cwd=HERE, capture_output=True, text=True); print(r.stdout.strip()[-3000:])
    if r.returncode: print(r.stderr[-3000:]); raise SystemExit(f'сбой: {a}')
def mockchain():
    """Тег сухого прогона — orgmock (не путать с run/mock_out.json матрёшки). Зёрна — пространство 'mock' соли, не пересекается с eval/hold."""
    sh('python3', 'tasks.py', 'salt')
    sh('python3', 'tasks.py', 'nested', 'orgmock', 'mock', '10')
    sh('python3', 'tasks.py', 'calib2', 'orgmock_ctasks')
    sh('python3', 'org.py', 'build-calib', 'orgmock_calib2', 'orgmock_ctasks')
    sh('node', 'run/mock_org.mjs', 'run/orgmock_calib2.js', 'run/orgmock_calib2_out.json')
    sh('python3', 'org.py', 'freeze', 'orgmock', 'run/orgmock_calib2_out.json')
    sh('python3', 'org.py', 'build', 'orgmock')
    sh('node', 'run/mock_org.mjs', 'run/orgmock.js', 'run/orgmock_out.json')
    sh('python3', 'org.py', 'analyze', 'orgmock', 'run/orgmock_out.json', 'orgmock')

if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'plan': b = budget(); print_budget(b); json.dump(b, open(f'{HERE}/run/budget.json', 'w'), ensure_ascii=False, indent=1)
    elif a[0] == 'build-calib': build_calib(a[1], a[2])
    elif a[0] == 'freeze': freeze(a[1], a[2] if os.path.isabs(a[2]) else f'{HERE}/{a[2]}')
    elif a[0] == 'build': build(a[1])
    elif a[0] == 'analyze': analyze(a[1], a[2] if os.path.isabs(a[2]) else f'{HERE}/{a[2]}', a[3])
    elif a[0] == 'mockchain': mockchain()
