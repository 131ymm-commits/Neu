# «Экосистема решателей» (совет 20): ресурс — свежий корм каждое поколение, борьба за него, энергия, смерть, деление, мутатор-голова.
#   python3 eco.py gen0 <stage1_out.json>     → eco/<run>/state.json: поколение 0 (дедупликация, ранжирование на калибровочном наборе, 12 лучших)
#   python3 eco.py probe                      → детерминизм, чувствительность к зерну, δ, доля ничьих (до пилота)
#   python3 eco.py step <t> [<births_out.json>] → принять потомков, оценить популяцию на корме t, энергия/смерть/деление, eco/<run>/births<t>.js
#   python3 eco.py holdout <t>                → лучшая по корму особь на отложенном наборе (отчёт; отбор его не видит)
import json, os, sys, re, hashlib, random, statistics as st
from concurrent.futures import ProcessPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from core import run_solver, greedy, gen_mkp
from eco_sets import inst as mk_inst, feed as mk_feed, CLASSES
RUN = os.path.join(HERE, 'eco', os.environ.get('ECO_RUN', 'pilot')); os.makedirs(RUN, exist_ok=True)
FEED_BASE = int(os.environ.get('ECO_FEED', 900000))
CAP, M, PRIZE, START_E, BIRTH_E, GIVE, KEEP, CHILD_E, MAX_BIRTHS, P_CROSS = 12, 12, 10.0, 10.0, 30.0, 20.0, 10.0, 10.0, 6, 0.3
CPU = 10
def J(p, d=None): return json.load(open(p)) if os.path.exists(p) else d
def W(p, o): json.dump(o, open(p, 'w'), ensure_ascii=False, indent=1)
SP = os.path.join(RUN, 'state.json')
def norm_hash(code):
    c = re.sub(r'#[^\n]*', '', code); c = re.sub(r'\s+', ' ', c).strip(); return hashlib.sha256(c.encode()).hexdigest()[:16]
def _eval(a):
    code, I, seed, core = a; r = run_solver(code, I, CPU, args=(seed,), core=core); return (r['value'] if r['ok'] else None, r['cpu'], r.get('err'))
def eval_many(pairs):
    """pairs: [(code, inst, seed)] → [(value|None, cpu, err)]; 3 процесса на ядрах 1..3"""
    args = [(c, I, s, 1 + k % 3) for k, (c, I, s) in enumerate(pairs)]
    with ProcessPoolExecutor(3) as ex: return list(ex.map(_eval, args))

def gen0(path):
    d = J(path); out = d.get('out', d); seen = {}; cands = []
    for k, v in out.items():
        if not v or not v.get('code'): continue
        h = norm_hash(v['code'])
        if h in seen: continue
        seen[h] = k; cands.append(dict(src=k, code=v['code'], notes=v.get('notes', ''), hash=h))
    cal = J(os.path.join(HERE, 'eco', 'calib_set.json')); CI = [mk_inst(c['seed'], c['klass']) for c in cal]
    res = eval_many([(c['code'], I, I['seed']) for c in cands for I in CI])
    for j, c in enumerate(cands):
        xs = res[j * len(CI):(j + 1) * len(CI)]
        c['calib_excess'] = [(x[0] - cal[i]['greedy']) if x[0] is not None else -10**9 for i, x in enumerate(xs)]
        c['calib_median'] = st.median(c['calib_excess'])
    cands.sort(key=lambda c: -c['calib_median']); top = cands[:CAP]
    pop = [dict(id=f'g0_{i}', lineage=f'L{i}', code=c['code'], notes=c['notes'], hash=c['hash'], energy=START_E, born=0, parents=[c['src']]) for i, c in enumerate(top)]
    W(SP, dict(t=0, pop=pop, dead=[], log=[], gen0_rank=[dict(src=c['src'], median=c['calib_median'], hash=c['hash']) for c in cands]))
    print('кандидатов', len(cands), 'взято', len(pop)); [print(' ', c['src'], c['calib_median']) for c in cands]

def probe():
    s = J(SP); pop = s['pop'][:5]; cal = J(os.path.join(HERE, 'eco', 'calib_set.json'))[::3][:3]; CI = [mk_inst(c['seed'], c['klass']) for c in cal]
    same = eval_many([(p['code'], I, 7) for p in pop for I in CI for _ in range(2)])
    det = sum(same[2 * k][0] != same[2 * k + 1][0] for k in range(len(same) // 2))
    seeds = [11, 12, 13, 14, 15]
    R = eval_many([(p['code'], I, sd) for p in pop for I in CI for sd in seeds])
    V = {}; k = 0
    for pi in range(len(pop)):
        for ii in range(len(CI)):
            V[(pi, ii)] = [R[k + j][0] for j in range(len(seeds))]; k += len(seeds)
    diffs = [abs(a - b) for v in V.values() for a in v for b in v if a is not None and b is not None and a != b] or [0]
    diffs_all = sorted(abs(a - b) for v in V.values() for i, a in enumerate(v) for b in v[i + 1:] if a is not None and b is not None)
    p95 = diffs_all[int(0.95 * (len(diffs_all) - 1))] if diffs_all else 0
    changes = 0; tot = 0
    for ii in range(len(CI)):
        wins = []
        for j in range(len(seeds)):
            vals = [V[(pi, ii)][j] or 0 for pi in range(len(pop))]; wins.append(vals.index(max(vals)))
        changes += sum(w != wins[0] for w in wins[1:]); tot += len(wins) - 1
    delta = max(p95, 0.0002 * st.median([c['greedy'] for c in cal]))
    ties = []
    for ii in range(len(CI)):
        vals = [V[(pi, ii)][0] or 0 for pi in range(len(pop))]; b = max(vals); ties.append(sum(v >= b - delta for v in vals))
    res = dict(nondeterministic_pairs=det, pairs=len(same) // 2, seed_diff_p95=p95, delta=delta, winner_change_share=changes / tot, within_delta_counts=ties)
    s['probe'] = res; W(SP, s); print(json.dumps(res, ensure_ascii=False))

def mutator_prompt(ind, table, other=None):
    from tourney import TASK
    rows = '\n'.join(f"  экземпляр {i + 1} (класс «{CLASSES[r['klass']][0]}/{CLASSES[r['klass']][1]}»): твоя ценность {r['own']}, жадный {r['greedy']}, лучший соперник {r['best_other']}" for i, r in enumerate(table))
    base = (f"Ты — мутатор в экосистеме решателей. {TASK.split('Для проверки у тебя есть')[0]}\n"
            "Решатели живут в популяции и борются за ресурс: каждое поколение приходят 12 свежих экземпляров четырёх классов (теснота рюкзаков 0,3 или 0,6 × связь ценности с весом слабая или сильная); "
            "экземпляр достаётся тем, кто решил его лучше всех, у кого нет пищи — умирает. Твоя задача — сделать потомка, который будет добывать больше.\n\n"
            f"Работай только в каталоге /tmp/eco/{ind['child_id']} (создай его); можно писать и запускать код; для проверки сгенерируй свои экземпляры похожего вида. Не открывай другие файлы и каталоги (ни репозиторий, ни /root). Готовые решатели из pip не ставь.\n\n"
            f"Результаты родителя в прошлом поколении:\n{rows}\n\nКод родителя:\n```python\n{ind['code']}\n```\nЗаметки родителя: {ind.get('notes', '')}\n")
    if other: base += f"\nЭто скрещивание. Второй родитель (другая линия, ведёт себя иначе):\n```python\n{other['code']}\n```\nЕго заметки: {other.get('notes', '')}\nСоедини их сильные стороны.\n"
    return base + "\nВерни: code — полный текст решателя-потомка; notes — коротко (до 150 слов), что изменил и почему."
SCHEMA = {'type': 'object', 'properties': {'code': {'type': 'string'}, 'notes': {'type': 'string'}}, 'required': ['code', 'notes']}

def step(t, births_path=None):
    s = J(SP); pop = s['pop']; delta = s['probe']['delta']; rng = random.Random(1000 + t)
    if births_path:   # принять потомков поколения t−1
        out = J(births_path); out = out.get('out', out); hashes = {p['hash'] for p in pop}
        for b in s.get('pending', []):
            v = out.get(b['child_id']) or {}
            code = v.get('code') or ''; h = norm_hash(code) if code else None
            if not code or h in hashes: s['log'].append(dict(t=t, event='child_lost', id=b['child_id'], reason='нет кода' if not code else 'дубликат')); continue
            pop.append(dict(id=b['child_id'], lineage=b['lineage'], code=code, notes=v.get('notes', ''), hash=h, energy=CHILD_E, born=t, parents=b['parents'])); hashes.add(h)
        s['pending'] = []
        while len(pop) > CAP:   # переполнение: умирает самый бедный
            p = min(pop, key=lambda p: p['energy']); pop.remove(p); s['dead'].append(dict(p, died=t, cause='теснота'))
    F = mk_feed(FEED_BASE, t, M)
    greedy_vals = [greedy(I, CPU, 0)['value'] for I in F]
    R = eval_many([(p['code'], I, I['seed']) for p in pop for I in F])
    X = {p['id']: [R[k * M + i][0] for i in range(M)] for k, p in enumerate(pop)}
    CPUU = {p['id']: st.mean(min(1.0, R[k * M + i][1] / CPU) for i in range(M)) for k, p in enumerate(pop)}
    income = {p['id']: 0.0 for p in pop}; ties = 0; winners = []
    for i in range(M):
        vals = {pid: X[pid][i] for pid in X if X[pid][i] is not None}
        if not vals: winners.append([]); continue
        b = max(vals.values()); w = [pid for pid, v in vals.items() if v >= b - delta]
        for pid in w: income[pid] += PRIZE / len(w)
        ties += len(w) > 1; winners.append(w)
    for p in pop: p['energy'] += income[p['id']] - (3.0 + 1.0 * CPUU[p['id']])
    alive = []
    for p in pop:
        if p['energy'] <= 0: s['dead'].append(dict(p, died=t, cause='голод'))
        else: alive.append(p)
    pop = alive
    # деление: энергия > порога, не больше MAX_BIRTHS, богатые первыми
    births = []; jobs = []
    for p in sorted([p for p in pop if p['energy'] > BIRTH_E], key=lambda p: -p['energy'])[:MAX_BIRTHS]:
        p['energy'] -= GIVE; cid = f"g{t + 1}_{p['id']}_{len(births)}"
        table = [dict(klass=F[i]['klass'], own=X[p['id']][i], greedy=greedy_vals[i], best_other=max([X[q][i] for q in X if q != p['id'] and X[q][i] is not None], default=None)) for i in range(M)]
        other = None
        if rng.random() < P_CROSS:
            cand = [q for q in pop if q['lineage'] != p['lineage']]
            if cand:
                def dist(q): return sum(abs((X[p['id']][i] or 0) - (X[q['id']][i] or 0)) for i in range(M))
                other = max(cand, key=dist)
        ind = dict(p, child_id=cid)
        jobs.append(dict(id=cid, prompt=mutator_prompt(ind, table, other)))
        births.append(dict(child_id=cid, lineage=p['lineage'], parents=[p['id']] + ([other['id']] if other else [])))
    s['pending'] = births; s['pop'] = pop; s['t'] = t
    wins_by_lineage = {}
    for i, w in enumerate(winners):
        for pid in w:
            L = next((p['lineage'] for p in pop + s['dead'] if p['id'] == pid), '?'); wins_by_lineage.setdefault(L, [0, 0, 0, 0]); wins_by_lineage[L][F[i]['klass']] += PRIZE / len(w)
    rec = dict(t=t, n=len(pop), births=len(births), crosses=sum(len(b['parents']) > 1 for b in births), ties_share=ties / M,
               deaths_hunger=sum(1 for d in s['dead'] if d['died'] == t and d['cause'] == 'голод'), deaths_crowd=sum(1 for d in s['dead'] if d['died'] == t and d['cause'] == 'теснота'),
               lineages=len({p['lineage'] for p in pop}), energy={p['id']: round(p['energy'], 2) for p in pop}, income={k: round(v, 2) for k, v in income.items()},
               wins_by_lineage=wins_by_lineage, excess_median={pid: st.median([(x - g) if x is not None else -10**6 for x, g in zip(X[pid], greedy_vals)]) for pid in X},
               cpu_frac=CPUU, feed_seeds=[I['seed'] for I in F])
    s['log'].append(rec); W(SP, s)
    src = (f"export const meta = {{ name: 'eco-{os.path.basename(RUN)}-births{t}', description: 'Экосистема ({os.path.basename(RUN)}), поколение {t}: деление (мутатор)', phases: [{{ title: 'Ход' }}] }}\n"
           f"const JOBS = {json.dumps(jobs, ensure_ascii=False)}\nconst S = {json.dumps(SCHEMA)}\nphase('Ход')\n"
           "const res = await parallel(JOBS.map(j => () => agent(j.prompt, {label: j.id, phase: 'Ход', schema: S})))\n"
           "const out = {}\nJOBS.forEach((j, i) => { out[j.id] = res[i] })\nreturn {out}\n")
    open(os.path.join(RUN, f'births{t}.js'), 'w').write(src)
    print(json.dumps({k: rec[k] for k in ('t', 'n', 'births', 'crosses', 'ties_share', 'deaths_hunger', 'deaths_crowd', 'lineages')}, ensure_ascii=False))
    print('энергия', rec['energy']); print('доход', rec['income'])

def holdout(t):
    s = J(SP); H = J('/root/solvers_secret/eco_holdout.json')['items']; pop = s['pop']
    last = s['log'][-1]; bestid = max(pop, key=lambda p: last['excess_median'].get(p['id'], -1e18))['id']; p = next(q for q in pop if q['id'] == bestid)
    HI = [mk_inst(h['seed'], h['klass']) for h in H]
    R = eval_many([(p['code'], I, I['seed']) for I in HI])
    g = [((h['ref'] - (r[0] if r[0] is not None else 0)) / (h['ref'] - h['greedy'])) for h, r in zip(H, R)]
    rec = dict(t=t, best=bestid, lineage=p['lineage'], median_g=st.median(g), g=g)
    s.setdefault('holdout', []).append(rec); W(SP, s); print(json.dumps(dict(t=t, best=bestid, median_g=rec['median_g']), ensure_ascii=False))

if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'gen0': gen0(sys.argv[2])
    elif c == 'probe': probe()
    elif c == 'step': step(int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None)
    elif c == 'holdout': holdout(int(sys.argv[2]))
