# DUEL-01: управление турниром. Правда контрольного набора — вне репозитория; правда задач раунда считается после составления.
#   init | bench0 | collect_bench0 <out> | set <r> | collect_set <r> <out> | solve <r> | collect_solve <r> <out>
#   strategy <r> | collect_strategy <r> <out> | bench1 | collect_bench1 <out>
import json, os, sys, math, hashlib, random
from duel_q import validate, truth, text, LIMITS
from hive_q import make
from hive_core import score_q

HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, os.environ.get('DUEL_RUN', 'run')); SECRET = '/root/duel_secret/' + os.environ.get('DUEL_RUN', 'run')
PLAYERS = ['D1', 'D2', 'D3', 'D4']
N_TASKS = 2
NO_TOOLS = 'Не используй никакие инструменты и не открывай файлы: рассуждай сам, опираясь только на текст ниже.'
BENCH_SEED = 7000


def J(p, x=None):
    if x is None: return json.load(open(p))
    json.dump(x, open(p, 'w'), ensure_ascii=False, indent=1)


def bundle(tag, args):
    src = open(os.path.join(HERE, 'duel_step.js')).read(); head, body = src.split('\n// ARGS.mode', 1)
    open(f'{D}/{tag}.js', 'w').write(head.replace("name: 'duel-step'", f"name: 'duel-{tag}'") + f'\nconst ARGS = {json.dumps(args, ensure_ascii=False)}\n// ARGS.mode' + body)
    print(tag, 'собран')


def clean(x):
    e = x.get('estimate'); lo = x.get('lo'); hi = x.get('hi')
    e = e if isinstance(e, (int, float)) and math.isfinite(e) and e > 0 else 1
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in (lo, hi)) or lo > hi or not (lo <= e <= hi): lo = hi = e
    return dict(estimate=e, lo=lo, hi=hi)


def IS(t, x):
    x = clean(x or {}); return score_q(t, x['estimate'], x['lo'], x['hi'])['interval_score']


def init():
    os.makedirs(D, exist_ok=True); os.makedirs(SECRET, exist_ok=True)
    bench = [dict(make(f, BENCH_SEED + i), id=f'{f}-{BENCH_SEED + i}') for f in ('COL3', 'PART', 'TWIN', 'SUB5') for i in range(5)]
    J(f'{SECRET}/bench.json', bench)
    J(f'{D}/bench_public.json', [dict(id=q['id'], text=q['text']) for q in bench])
    J(f'{D}/state.json', dict(r=0, players={p: dict(notes=[]) for p in PLAYERS}, digest='', points={p: 0.0 for p in PLAYERS}))
    J(f'{D}/freeze.json', dict(bench_sha256=hashlib.sha256(json.dumps(bench, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                               files={f: hashlib.sha256(open(os.path.join(HERE, f), 'rb').read()).hexdigest() for f in ('duel_q.py', 'duel_step.js', 'duel_run.py', 'duel_analyze.py')}))
    print('контрольный набор', len(bench))


def bench_score(out):
    bench = {q['id']: q for q in J(f'{SECRET}/bench.json')}
    res = {}
    for nm, r in out['out'].items():
        items = {x['id']: x for x in ((r or {}).get('items') or [])}
        res[nm] = {i: (IS(q['truth'], items.get(i)) if i in items else None) for i, q in bench.items()}
    return res


def set_(r):
    st = J(f'{D}/state.json')
    bundle(f'set{r}', dict(mode='set', players={p: dict(notes=st['players'][p]['notes']) for p in PLAYERS}, limits=LIMITS, n_tasks=N_TASKS, no_tools=NO_TOOLS))


def collect_set(r, path):
    out = J(path); J(f'{D}/raw_set{r}.json', out)
    tasks = []
    for p in PLAYERS:
        for k, t in enumerate(((out['out'].get(p) or {}).get('tasks') or [])[:N_TASKS]):
            try: params = json.loads(t.get('params') or '')
            except Exception: params = None
            q, err = validate(t.get('family'), params) if isinstance(params, dict) else (None, 'JSON')
            v = truth(t['family'], q) if q else None
            if q and t['family'] in ('COL3', 'SUB') and not v: q, err = None, 'нет решений'
            tasks.append(dict(id=f'R{r}{p}T{k + 1}', setter=p, family=t.get('family'), params=q, error=err, truth=v,
                              text=text(t['family'], q) if q else None, setter_answer=clean(t), setter_IS=IS(v, t) if q else None, why=t.get('why')))
    J(f'{D}/tasks{r}.json', tasks)
    for t in tasks: print(t['id'], t['family'], 'ОТКАЗ: ' + t['error'] if t['error'] else f"правда {t['truth']}, составитель {t['setter_answer']['estimate']:.4g} IS {t['setter_IS']:.3f}")


def solve(r):
    st = J(f'{D}/state.json'); tasks = [t for t in J(f'{D}/tasks{r}.json') if t['params']]
    bundle(f'solve{r}', dict(mode='solve', players={p: dict(notes=st['players'][p]['notes']) for p in PLAYERS},
                             tasks={p: [dict(id=t['id'], text=t['text']) for t in tasks if t['setter'] != p] for p in PLAYERS}, no_tools=NO_TOOLS))


def collect_solve(r, path):
    out = J(path); J(f'{D}/raw_solve{r}.json', out)
    tasks = J(f'{D}/tasks{r}.json'); st = J(f'{D}/state.json')
    ans = {p: {x['id']: x for x in ((out['out'].get(p) or {}).get('items') or [])} for p in PLAYERS}
    score = {p: dict(set_pts=0.0, solve_IS=[], invalid=0) for p in PLAYERS}
    for t in tasks:
        if not t['params']:
            score[t['setter']]['invalid'] += 1; score[t['setter']]['set_pts'] -= 1.0; continue  # штраф за негодную задачу
        t['solvers'] = {p: dict(answer=clean(ans[p].get(t['id']) or {}), IS=IS(t['truth'], ans[p].get(t['id']))) for p in PLAYERS if p != t['setter']}
        m = sum(x['IS'] for x in t['solvers'].values()) / len(t['solvers'])
        t['setter_points'] = m - t['setter_IS']; score[t['setter']]['set_pts'] += t['setter_points']
        for p, x in t['solvers'].items(): score[p]['solve_IS'].append(x['IS'])
    for p in PLAYERS:
        s = score[p]; s['solve_IS'] = sum(s['solve_IS']) / len(s['solve_IS']) if s['solve_IS'] else None
        st['points'][p] += s['set_pts'] - (s['solve_IS'] or 0)
    J(f'{D}/tasks{r}.json', tasks); J(f'{D}/score{r}.json', score)
    st['digest'] = (st['digest'] + '\n' if st['digest'] else '') + '\n'.join(f"{t['text']} Правда: {t['truth']}." for t in tasks if t['params'])
    J(f'{D}/state.json', st)
    print('раунд', r, {p: (round(score[p]['set_pts'], 3), round(score[p]['solve_IS'] or 0, 3)) for p in PLAYERS})


def strategy(r):
    st = J(f'{D}/state.json'); tasks = J(f'{D}/tasks{r}.json'); score = J(f'{D}/score{r}.json')
    lines = []
    for t in tasks:
        if not t['params']: lines.append(f"[{t['id']}] составитель {t['setter']}: задача отклонена судьёй ({t['error']}), штраф 1."); continue
        lines.append(f"[{t['id']}] составитель {t['setter']}: {t['text']} Правда: {t['truth']}. Составитель: {t['setter_answer']['estimate']:.5g} [{t['setter_answer']['lo']:.4g}; {t['setter_answer']['hi']:.4g}], балл {t['setter_IS']:.3f}. " +
                     '; '.join(f"{p}: {x['answer']['estimate']:.5g} [{x['answer']['lo']:.4g}; {x['answer']['hi']:.4g}], балл {x['IS']:.3f}" for p, x in t['solvers'].items()) +
                     f". Очки составителя {t['setter_points']:+.3f}.")
    table = '\n'.join(f"{p}: очки составителя {score[p]['set_pts']:+.3f}, средний балл решателя {score[p]['solve_IS'] if score[p]['solve_IS'] is None else round(score[p]['solve_IS'], 3)}, всего очков {st['points'][p]:+.3f}" for p in PLAYERS)
    fb = '\n'.join(lines) + '\n\nИтог раунда:\n' + table
    bundle(f'strategy{r}', dict(mode='strategy', players={p: dict(notes=st['players'][p]['notes']) for p in PLAYERS}, feedback={p: f'Ты — {p}.\n' + fb for p in PLAYERS}, no_tools=NO_TOOLS))


def collect_strategy(r, path):
    out = J(path); J(f'{D}/raw_strategy{r}.json', out); st = J(f'{D}/state.json')
    for p in PLAYERS:
        n = ((out['out'].get(p) or {}).get('notes'))
        if isinstance(n, list): st['players'][p]['notes'] = [str(x) for x in n[:6]]
    st['r'] = r + 1; J(f'{D}/state.json', st); print('стратегии обновлены')


def bench(tag):
    st = J(f'{D}/state.json'); qs = J(f'{D}/bench_public.json')
    if tag == 'bench0':
        players = {'B0a': dict(notes=[], digest=''), 'B0b': dict(notes=[], digest='')}
    else:
        players = {p: dict(notes=st['players'][p]['notes'], digest=st['digest']) for p in PLAYERS}
        players.update(C=dict(notes=[], digest=st['digest']), B0=dict(notes=[], digest=''))
    bundle(tag, dict(mode='bench', questions=qs, players=players, no_tools=NO_TOOLS))


def collect_bench(tag, path):
    out = J(path); J(f'{D}/raw_{tag}.json', out); res = bench_score(out); J(f'{D}/{tag}_scores.json', res)
    print(tag, {k: round(sum(v for v in s.values() if v is not None) / max(1, sum(v is not None for v in s.values())), 3) for k, s in res.items()})


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'init': init()
    elif c in ('bench0', 'bench1'): bench(c)
    elif c in ('collect_bench0', 'collect_bench1'): collect_bench(c.split('_')[1], sys.argv[2])
    elif c == 'set': set_(int(sys.argv[2]))
    elif c == 'collect_set': collect_set(int(sys.argv[2]), sys.argv[3])
    elif c == 'solve': solve(int(sys.argv[2]))
    elif c == 'collect_solve': collect_solve(int(sys.argv[2]), sys.argv[3])
    elif c == 'strategy': strategy(int(sys.argv[2]))
    elif c == 'collect_strategy': collect_strategy(int(sys.argv[2]), sys.argv[3])
