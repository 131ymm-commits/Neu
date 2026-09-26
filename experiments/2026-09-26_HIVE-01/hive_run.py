# HIVE-01: управление прогоном по поколениям (решение совета, заседание 5).
# Правда хранится только в SECRET (вне репозитория) и в workflow не попадает. После каждого поколения в run/ пишутся баллы
# и правда уже пройденных вопросов; будущих и отложенных — никогда до итоговой проверки.
#   init | ans <g> | collect_ans <g> <out.json> | leg <g> | collect_leg <g> <out.json> | test | collect_test <out.json>
import json, os, sys, math, statistics, hashlib
from hive_q import make, FAMS
from hive_core import SEED_LAWS, ROLES, score_q

HERE = os.path.dirname(os.path.abspath(__file__))
SECRET = '/root/hive_secret'
N_GENS, GEN_SEED, TEST_SEED = 5, 1000, 5000
NO_TOOLS = 'Не используй никакие инструменты и не открывай файлы: оценивай сам, опираясь только на текст ниже.'
INIT = dict(laws=[SEED_LAWS[0], SEED_LAWS[1], SEED_LAWS[6], SEED_LAWS[8]], roles=ROLES[:3], delphi=False, agg='median', personal=[[], [], []])
SELF = ['A', 'B']
CAP = 200                      # потолок вызовов основного прогона (технические повторы не считаются)
WORST_GEN = 2 * 7 + 3 + 3 + 2 * (3 + 1 + 1 + 3)   # ответ: A, B до 7 (пересмотр + мозолистое тело), F, F+ по 3; законодательство A, B по 8
TEST_RESERVE = 2 * 7 + 3 + 3 + 3 + 1               # A, B до 7; F+ 3; F дважды по 3; S 1


def used_calls(D):
    """Счётчик по сырым журналам: число вызовов без технических повторов."""
    n = 0
    for f in sorted(os.listdir(D)):
        if f.startswith(('raw_ans', 'raw_leg')) and f.endswith('.json'):
            n += sum(1 for r in J(f'{D}/{f}')['records'] if not r.get('retry'))
    return n


def can_start_gen(D):
    u = used_calls(D)
    return u + WORST_GEN + TEST_RESERVE <= CAP, u


def J(p, x=None):
    if x is None: return json.load(open(p))
    json.dump(x, open(p, 'w'), ensure_ascii=False, indent=1)


def sha(x): return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def init(D):
    os.makedirs(SECRET, exist_ok=True); os.makedirs(D, exist_ok=True)
    gens = [[dict(make(f, GEN_SEED + 100 * g + i), id=f'{f}-{GEN_SEED + 100 * g + i}') for f in FAMS for i in range(2)] for g in range(N_GENS)]
    conf = [dict(make(f, TEST_SEED + i), id=f'{f}-{TEST_SEED + i}') for f in FAMS if f != 'COLLATZ' for i in range(5)]
    ctrl = [dict(make('COLLATZ', TEST_SEED + i), id=f'COLLATZ-{TEST_SEED + i}') for i in range(4)]
    full = dict(gens=gens, test_conf=conf, test_ctrl=ctrl)
    J(f'{SECRET}/questions_full.json', full)
    pub = lambda qs: [dict(id=q['id'], fam=q['fam'], text=q['text']) for q in qs]
    J(f'{D}/questions_public.json', dict(gens=[pub(g) for g in gens], test=pub(conf + ctrl)))
    J(f'{D}/state.json', dict(g=0, hives={k: json.loads(json.dumps(INIT)) for k in ['A', 'B', 'Fp', 'F']}, digest=''))
    J(f'{D}/freeze.json', dict(questions_sha256=sha(full), test_ids=[q['id'] for q in conf + ctrl],
                               files={f: hashlib.sha256(open(os.path.join(HERE, f), 'rb').read()).hexdigest() for f in
                                      ('hive_q.py', 'hive_core.py', 'hive_step.js', 'hive_run.py', 'hive_analyze.py', 'verify_truth.py')},
                               temperature='по умолчанию, не контролируется'))
    print('вопросов: поколения', sum(map(len, gens)), 'тест', len(conf), '+', len(ctrl), 'хеш', sha(full)[:12])


def bundle(D, tag, args):
    src = open(os.path.join(HERE, 'hive_step.js')).read()
    head, body = src.split('\n// ARGS.mode', 1)
    open(f'{D}/{tag}.js', 'w').write(head.replace("name: 'hive-step'", f"name: 'hive-{tag}'") + f'\nconst ARGS = {json.dumps(args, ensure_ascii=False)}\n// ARGS.mode' + body)
    J(f'{D}/{tag}_args.json', args)
    print(tag, 'собран')


def ans(D, g):
    ok, u = can_start_gen(D)
    if not ok:
        print(f'СТОП: использовано {u}, худший случай поколения {WORST_GEN} + резерв теста {TEST_RESERVE} > {CAP}; поколение {g} не начинается'); sys.exit(3)
    st = J(f'{D}/state.json'); qs = J(f'{D}/questions_public.json')['gens'][g]
    hv = {k: st['hives'][k] for k in ('A', 'B', 'Fp', 'F')}
    dg = {k: (st['digest'] if k in ('A', 'B', 'Fp') else '') for k in hv}
    bundle(D, f'ans{g}', dict(mode='answer', questions=[dict(id=q['id'], text=q['text']) for q in qs], hives=hv, digests=dg, no_tools=NO_TOOLS))


def final_of(o, ids):
    """Итог улья: мозолистое тело, если было; иначе медиана голов в логарифмах. Недостающее — вырожденный интервал [1, 1]."""
    heads = o.get('second') or o.get('first') or []
    hm = [{x['id']: x for x in (b or {}).get('items', [])} for b in heads]
    cal = {x['id']: x for x in ((o.get('cal') or {}).get('items') or [])}
    L = lambda v: math.log(max(v, 1e-9))
    out = {}; missing = set()
    for i in ids:
        x = cal.get(i)
        if x is None:
            xs = [m[i] for m in hm if i in m]
            if not xs: missing.add(i)
            x = dict(estimate=math.exp(statistics.median(L(y['estimate']) for y in xs)), lo=math.exp(statistics.median(L(y['lo']) for y in xs)),
                     hi=math.exp(statistics.median(L(y['hi']) for y in xs))) if xs else dict(estimate=1, lo=1, hi=1)
        out[i] = clean(x)
    final_of.missing = missing
    return out, hm


def clean(x):
    """Правила крайних случаев: оценка ≤ 0 → 1; испорченный интервал → [оценка, оценка]."""
    e = x.get('estimate'); lo = x.get('lo'); hi = x.get('hi')
    e = e if isinstance(e, (int, float)) and math.isfinite(e) and e > 0 else 1
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in (lo, hi)) or lo > hi or not (lo <= e <= hi): lo = hi = e
    return dict(estimate=e, lo=lo, hi=hi)


def collect_ans(D, g, path):
    full = J(f'{SECRET}/questions_full.json')['gens'][g]; truth = {q['id']: q for q in full}
    out = J(path); J(f'{D}/raw_ans{g}.json', out)
    res = {}
    for k, o in out['out'].items():
        fin, hm = final_of(o, list(truth))
        rows = [dict(id=i, fam=truth[i]['fam'], truth=truth[i]['truth'], final=fin[i], heads=[m.get(i) for m in hm], **score_q(truth[i]['truth'], fin[i]['estimate'], fin[i]['lo'], fin[i]['hi'])) for i in truth]
        res[k] = dict(rows=rows, IS=sum(r['interval_score'] for r in rows) / len(rows), coverage=sum(r['covered'] for r in rows) / len(rows))
    J(f'{D}/res{g}.json', res)
    print('поколение', g, {k: round(v['IS'], 3) for k, v in res.items()})


def fmt_rows(rows):
    return '\n'.join(f"[{r['id']}] правда {r['truth']}; итог {r['final']['estimate']:.5g} [{r['final']['lo']:.4g}; {r['final']['hi']:.4g}] — "
                     f"{'попал' if r['covered'] else 'ПРОМАХ'}, ошибка {100 * (math.exp(r['ignorance']) - 1):.1f} %" for r in rows)


def leg(D, g):
    res = J(f'{D}/res{g}.json'); st = J(f'{D}/state.json')
    fb, others = {}, {}
    for k in SELF:
        rows = res[k]['rows']
        fb[k] = fmt_rows(rows) + f"\nСредний интервальный балл улья {res[k]['IS']:.3f} (меньше — лучше), покрытие {100 * res[k]['coverage']:.0f} %."
        nh = len(st['hives'][k]['roles'])
        others[k] = [f'Голова {j + 1}:\n' + '\n'.join(f"[{r['id']}] " + (f"{r['heads'][j]['estimate']:.5g} [{r['heads'][j]['lo']:.4g}; {r['heads'][j]['hi']:.4g}] — {r['heads'][j].get('note', '')}"
                                                                   if j < len(r['heads']) and r['heads'][j] else 'нет') for r in rows) for j in range(nh)]
    bundle(D, f'leg{g}', dict(mode='legislate', hives={k: st['hives'][k] for k in SELF}, feedback=fb, others=others, no_tools=NO_TOOLS, max_laws=8))


def collect_leg(D, g, path):
    out = J(path); J(f'{D}/raw_leg{g}.json', out)
    st = J(f'{D}/state.json'); res = J(f'{D}/res{g}.json')
    for k in SELF:
        st['hives'][k] = out['out'][k]['hive']
    # сводка для A, B и F+: одинаковый шаблон — правда и ошибки эталонного улья F по всем пройденным поколениям
    st['digest'] = (st['digest'] + '\n' if st['digest'] else '') + fmt_rows(res['F']['rows'])
    st['g'] = g + 1
    J(f'{D}/state.json', st)
    for k in SELF:
        L = out['out'][k]
        print(k, 'принято', len(L['adopted']), 'отклонено фильтром', len(L['rejected']), 'сгущений', len(L['concentrated']), 'законов', len(st['hives'][k]['laws']))


def test(D):
    st = J(f'{D}/state.json'); qs = J(f'{D}/questions_public.json')['test']
    single = dict(laws=[], roles=[None], delphi=False, agg='median', personal=[[]])
    hv = dict(A=st['hives']['A'], B=st['hives']['B'], Fp=st['hives']['Fp'], F1=st['hives']['F'], F2=st['hives']['F'], S=single)
    dg = dict(A=st['digest'], B=st['digest'], Fp=st['digest'], F1='', F2='', S='')
    bundle(D, 'test', dict(mode='answer', questions=[dict(id=q['id'], text=q['text']) for q in qs], hives=hv, digests=dg, no_tools=NO_TOOLS))


if __name__ == '__main__':
    cmd, D = sys.argv[1], os.path.join(HERE, 'run')
    if cmd == 'init': init(D)
    elif cmd == 'ans': ans(D, int(sys.argv[2]))
    elif cmd == 'collect_ans': collect_ans(D, int(sys.argv[2]), sys.argv[3])
    elif cmd == 'leg': leg(D, int(sys.argv[2]))
    elif cmd == 'collect_leg': collect_leg(D, int(sys.argv[2]), sys.argv[3])
    elif cmd == 'test': test(D)
