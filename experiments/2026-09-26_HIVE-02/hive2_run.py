# HIVE-02: природная эволюция ульев (слова человека: «эволюция и смерть как её двигатель»; «сначала много ресурса,
# ульи растут и делятся, потом кратное падение, и выживают лучшие»).
# Улей = 3 головы, медиана, без пересмотра — эволюционируют только законы. В каждом поколении все живые ульи отвечают
# на одни и те же 12 свежих вопросов (по 3 из COL3, PART, TWIN, SUB5; Коллатца нет — это чистый шум).
# Изобилие: каждый улей делится — остаётся сам и рождает потомка (его законы с мутацией). Численность 3 → 6 → 12.
# Падение: ёмкость среды падает вчетверо (12 → 3); выживают 3 лучших по баллу этого поколения. Цикл повторяется.
# Выжившие своих законов не меняют. Правда — вне репозитория.
#   init | ans <g> | collect_ans <g> <out> | next <g> (падение или сборка деления) | collect_birth <g> <out> | test
import json, os, sys, math, random, hashlib, statistics
from hive_q import make
from hive_core import SEED_LAWS, ROLES, score_q

HERE = os.path.dirname(os.path.abspath(__file__)); RUN = os.environ.get('HIVE2_RUN', 'run'); D = os.path.join(HERE, RUN)
SECRET = f'/root/hive2_secret/{RUN}'
FAMS = ['COL3', 'PART', 'TWIN', 'SUB5']
FOUNDERS, BOOM_MAX, BUST_KEEP, N_GENS, PER_FAM = 3, 12, 3, 6, 3
GEN_SEED, TEST_SEED, INIT_SEED = int(os.environ.get('HIVE2_GEN_SEED', 20000)), 25000, 2609291
NO_TOOLS = 'Не используй никакие инструменты и не открывай файлы: оценивай сам, опираясь только на текст ниже.'


def J(p, x=None):
    if x is None: return json.load(open(p))
    json.dump(x, open(p, 'w'), ensure_ascii=False, indent=1)


def hive(laws): return dict(laws=list(laws), roles=ROLES[:3], delphi=False, agg='median', personal=[[], [], []])


def init():
    os.makedirs(D, exist_ok=True); os.makedirs(SECRET, exist_ok=True)
    rng = random.Random(INIT_SEED)
    pop = {f'H{i + 1}': dict(hive=hive(rng.sample(SEED_LAWS, rng.randint(3, 5))), born=0, parents=[]) for i in range(FOUNDERS)}
    gens = [[dict(make(f, GEN_SEED + 100 * g + i), id=f'{f}-{GEN_SEED + 100 * g + i}') for f in FAMS for i in range(PER_FAM)] for g in range(N_GENS)]
    test = [dict(make(f, TEST_SEED + i), id=f'{f}-{TEST_SEED + i}') for f in FAMS for i in range(5)]
    J(f'{SECRET}/questions_full.json', dict(gens=gens, test=test))
    pub = lambda qs: [dict(id=q['id'], text=q['text']) for q in qs]
    J(f'{D}/questions_public.json', dict(gens=[pub(g) for g in gens], test=pub(test)))
    J(f'{D}/state.json', dict(g=0, pop=pop, next_id=FOUNDERS + 1, founders={k: v['hive']['laws'] for k, v in pop.items()}, graveyard=[], history=[]))
    J(f'{D}/freeze.json', dict(questions_sha256=hashlib.sha256(json.dumps(dict(gens=gens, test=test), ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                               files={f: hashlib.sha256(open(os.path.join(HERE, f), 'rb').read()).hexdigest() for f in ('hive_q.py', 'hive_core.py', 'hive2_step.js', 'hive2_run.py', 'hive2_analyze.py')},
                               temperature='по умолчанию, не контролируется'))
    print('популяция', list(pop), 'вопросов', sum(map(len, gens)), 'тест', len(test))


def bundle(tag, args):
    src = open(os.path.join(HERE, 'hive2_step.js')).read(); head, body = src.split('\n// ARGS.mode', 1)
    open(f'{D}/{tag}.js', 'w').write(head.replace("name: 'hive2-step'", f"name: 'hive2-{tag}'") + f'\nconst ARGS = {json.dumps(args, ensure_ascii=False)}\n// ARGS.mode' + body)
    print(tag, 'собран')


def clean(x):
    e = x.get('estimate'); lo = x.get('lo'); hi = x.get('hi')
    e = e if isinstance(e, (int, float)) and math.isfinite(e) and e > 0 else 1
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in (lo, hi)) or lo > hi or not (lo <= e <= hi): lo = hi = e
    return dict(estimate=e, lo=lo, hi=hi)


def final_of(o, ids):
    hm = [{x['id']: x for x in (b or {}).get('items', [])} for b in (o.get('first') or [])]
    L = lambda v: math.log(max(v, 1e-9)); out, missing = {}, set()
    for i in ids:
        xs = [m[i] for m in hm if i in m]
        if not xs: missing.add(i); out[i] = dict(estimate=1, lo=1, hi=1); continue
        out[i] = clean(dict(estimate=math.exp(statistics.median(L(y['estimate']) for y in xs)), lo=math.exp(statistics.median(L(y['lo']) for y in xs)),
                            hi=math.exp(statistics.median(L(y['hi']) for y in xs))))
    return out, hm, missing


def ans(g):
    st = J(f'{D}/state.json'); qs = J(f'{D}/questions_public.json')['gens'][g]
    bundle(f'ans{g}', dict(mode='answer', questions=qs, hives={k: v['hive'] for k, v in st['pop'].items()}, digests={}, no_tools=NO_TOOLS))


def fmt_rows(rows):
    return '\n'.join(f"[{r['id']}] правда {r['truth']}; итог {r['final']['estimate']:.5g} [{r['final']['lo']:.4g}; {r['final']['hi']:.4g}] — "
                     f"{'попал' if r['covered'] else 'ПРОМАХ'}, ошибка {100 * (math.exp(r['ignorance']) - 1):.1f} %" for r in rows)


def collect_ans(g, path):
    full = {q['id']: q for q in J(f'{SECRET}/questions_full.json')['gens'][g]}
    out = J(path); J(f'{D}/raw_ans{g}.json', out); st = J(f'{D}/state.json')
    res = {}
    for k, o in out['out'].items():
        fin, hm, miss = final_of(o, list(full))
        rows = [dict(id=i, truth=q['truth'], final=fin[i], **score_q(q['truth'], fin[i]['estimate'], fin[i]['lo'], fin[i]['hi'])) for i, q in full.items()]
        res[k] = dict(IS=sum(r['interval_score'] for r in rows) / len(rows), coverage=sum(r['covered'] for r in rows) / len(rows), missing=sorted(miss), rows=rows)
    J(f'{D}/res{g}.json', res)
    rank = sorted(res, key=lambda k: res[k]['IS'])
    st['history'].append(dict(g=g, IS={k: res[k]['IS'] for k in rank}, rank=rank, laws={k: st['pop'][k]['hive']['laws'] for k in rank}))
    J(f'{D}/state.json', st)
    print('поколение', g, ' '.join(f"{k}:{res[k]['IS']:.3f}" for k in rank))


def next_step(g):
    """После поколения g: падение (если численность достигла ёмкости изобилия) или деление всех ульев."""
    st = J(f'{D}/state.json'); res = J(f'{D}/res{g}.json')
    rank = sorted(res, key=lambda k: res[k]['IS'])
    if len(st['pop']) >= BOOM_MAX:
        dead = rank[BUST_KEEP:]
        for k in dead:
            st['graveyard'].append(dict(id=k, died=g, laws=st['pop'][k]['hive']['laws'], born=st['pop'][k]['born'], parents=st['pop'][k]['parents'])); del st['pop'][k]
        st['g'] = g + 1; st.setdefault('events', []).append(dict(g=g, kind='падение', survivors=rank[:BUST_KEEP], dead=dead))
        J(f'{D}/state.json', st)
        print('ПАДЕНИЕ после поколения', g, ': выжили', rank[:BUST_KEEP], '; умерли', len(dead)); return
    children = {}
    for i, k in enumerate(rank):
        children[f'H{st["next_id"] + i}'] = dict(parent=st['pop'][k]['hive'], feedback=fmt_rows(res[k]['rows']), parents=[k])
    J(f'{D}/birth{g}_plan.json', dict(rank=rank, dead=[], children={c: v['parents'] for c, v in children.items()}))
    bundle(f'birth{g}', dict(mode='birth', children={c: {kk: vv for kk, vv in v.items() if kk != 'parents'} for c, v in children.items()}, no_tools=NO_TOOLS))
    print('ИЗОБИЛИЕ после поколения', g, ': делятся все', len(children), 'ульев')


def collect_birth(g, path):
    out = J(path); J(f'{D}/raw_birth{g}.json', out); st = J(f'{D}/state.json'); plan = J(f'{D}/birth{g}_plan.json')
    for k, parents in plan['children'].items():
        st['pop'][k] = dict(hive=hive(out['out'][k]['laws']), born=g + 1, parents=parents, rejected=out['out'][k].get('rejected', []))
    st['next_id'] += len(plan['children']); st['g'] = g + 1
    st.setdefault('events', []).append(dict(g=g, kind='деление', children=plan['children']))
    J(f'{D}/state.json', st)
    print('родились', len(plan['children']), '; популяция', len(st['pop']))


def test():
    st = J(f'{D}/state.json'); qs = J(f'{D}/questions_public.json')['test']
    last = st['history'][-1]['rank']
    champ = [k for k in last if k in st['pop']][0]  # лучший выживший по последнему поколению (выбран до теста)
    founders = st['founders']; best_founder = st['history'][0]['rank'][0]
    hives = dict(CHAMP=st['pop'][champ]['hive'], FOUNDER=hive(founders[best_founder]), F=hive(SEED_LAWS[0:1] + [SEED_LAWS[1], SEED_LAWS[6], SEED_LAWS[8]]),
                 S=dict(laws=[], roles=[None], delphi=False, agg='median', personal=[[]]))
    h1 = os.path.join(HERE, '..', '2026-09-26_HIVE-01', 'run', 'state.json')
    if os.path.exists(h1):
        s1 = J(h1)
        for k in ('A', 'B'): hives[f'HIVE01_{k}'] = dict(s1['hives'][k], delphi=False)  # законы и личные правила HIVE-01, протокол уравнен
    J(f'{D}/test_plan.json', dict(champion=champ, best_founder=best_founder, arms=list(hives)))
    bundle('test', dict(mode='answer', questions=qs, hives=hives, digests={}, no_tools=NO_TOOLS))


if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'init': init()
    elif c == 'ans': ans(int(sys.argv[2]))
    elif c == 'collect_ans': collect_ans(int(sys.argv[2]), sys.argv[3])
    elif c == 'next': next_step(int(sys.argv[2]))
    elif c == 'collect_birth': collect_birth(int(sys.argv[2]), sys.argv[3])
    elif c == 'test': test()
