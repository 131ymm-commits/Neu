# PRECOND-01, пилот (до PREREG): 16 предусловий (план 2^(8−4), разрешение IV) × 6 задач × 1 голос = 96 вызовов, effort medium.
# Задачи WH_8001–8006 — из SELECT-01 main, в тест PRECOND-01 не войдут. Правда — SELECT-01: она раскрыта в 2026-10-13, и
# выборы SELECT-01 к тому времени были запушены. Пилот описательный: разброс, отказы, длина ответа, цена. Выводов нет.
#   python3 pilot_precond.py jobs | collect | analyze        (PRECOND_TAG=dry — сухой прогон на заглушках)
import collections, json, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); SEL = os.path.join(HERE, '..', '2026-10-07_SELECT-01')
sys.path.insert(0, SEL); sys.path.insert(0, HERE)
import harness as H, sim  # noqa: E402
from analyze import a0  # noqa: E402
import prompts_precond as PP  # noqa: E402
TAG = os.environ.get('PRECOND_TAG', 'pilot'); SEC = '/root/select_secret'
TASKS = [f'WH_{s}' for s in range(8001, 8007)]; DESIGN = PP.design(16)

def pool_of(t): return json.load(open(f'{SEL}/pools/{t}.json'))

def jobs():
    js = []
    for t in TASKS:
        tk = H.task(t); pool = pool_of(t); shown = [pool[j] for j in H.perm(t)]
        for c, on in enumerate(DESIGN):
            prompt, schema = PP.compose(set(on), sim.RULES[tk['type']](tk), shown)
            js.append(dict(id=f'{t}|P{c:02d}|0', prompt=prompt, schema=schema))
    with open(f'{HERE}/run/{TAG}_jobs.jsonl', 'w') as fh:
        for j in js: fh.write(json.dumps(j, ensure_ascii=False) + '\n')
    json.dump({f'P{c:02d}': on for c, on in enumerate(DESIGN)}, open(f'{HERE}/run/{TAG}_design.json', 'w'), ensure_ascii=False, indent=1)
    print(len(js), 'заданий')

def collect():
    os.makedirs(f'{HERE}/evals', exist_ok=True); seen = {}
    for r in map(json.loads, open(f'{HERE}/run/{TAG}_out.jsonl')):
        if r['id'] in seen and not seen[r['id']].get('error'): continue          # первая несбойная запись по id
        seen[r['id']] = r
    with open(f'{HERE}/evals/{TAG}.jsonl', 'w') as fh:
        for r in seen.values():
            t, p, i = r['id'].split('|'); pm = H.perm(t); res = r.get('result') or {}; c = res.get('choice')
            ch = None if r.get('error') else (-1 if c == -1 else (pm[c] if isinstance(c, int) and 0 <= c < len(pm) else 'недопустимый'))
            fh.write(json.dumps(dict(task=t, pre=p, choice=ch, p_best=res.get('p_best'), error=r.get('error'), out=r.get('out', 0),
                                     models=r.get('models')), ensure_ascii=False) + '\n')
    print(len(seen), 'выборов')

def analyze():
    on = json.load(open(f'{HERE}/run/{TAG}_design.json')); E = [json.loads(l) for l in open(f'{HERE}/evals/{TAG}.jsonl')]
    rows = []
    for e in E:
        tr = json.load(open(f'{SEC}/truth/{e["task"]}.json')); orc, mean = max(tr), st.mean(tr); reg = lambda i: (orc - tr[i]) / (orc - mean)
        c = e['choice']; refused = c == -1; valid = isinstance(c, int) and 0 <= c < len(tr)
        r = reg(c) if valid else (reg(a0(pool_of(e['task']), e['task'])) if refused else 1.0)   # отказ → A0, сбой/недопустимый → 1
        rows.append(dict(task=e['task'], pre=e['pre'], regret=r, refused=refused, lost=not valid and not refused, out=e['out'] or 0,
                         p_best=e['p_best'], hit=valid and tr[c] == orc))
    tmean = {t: st.mean(r['regret'] for r in rows if r['task'] == t) for t in TASKS}
    for r in rows: r['centered'] = r['regret'] - tmean[r['task']]
    by_pre = {p: [r for r in rows if r['pre'] == p] for p in on}
    effects = {}
    for f in PP.F:
        a = [r for r in rows if f in on[r['pre']]]; b = [r for r in rows if f not in on[r['pre']]]
        effects[f] = dict(regret=round(st.mean(x['centered'] for x in a) - st.mean(x['centered'] for x in b), 3),
                          out=round(st.mean(x['out'] for x in a) - st.mean(x['out'] for x in b)),
                          refusal=round(sum(x['refused'] for x in a) / len(a), 3))
    pre_means = {p: st.mean(r['centered'] for r in v) for p, v in by_pre.items() if v}
    resid = [r['centered'] - pre_means[r['pre']] for r in rows]
    conf = [(r['p_best'], r['hit']) for r in rows if r['p_best'] is not None and not r['refused']]
    out = dict(n=len(rows), lost=sum(r['lost'] for r in rows), refused=sum(r['refused'] for r in rows),
               mean_regret=round(st.mean(r['regret'] for r in rows), 3), sd_vote=round(st.pstdev([r['centered'] for r in rows]), 3),
               sd_resid=round(st.pstdev(resid), 3), sd_between_pre=round(st.pstdev(list(pre_means.values())), 3),
               out_per_call=round(st.mean(r['out'] for r in rows)), effects=effects,
               per_pre={p: dict(on=on[p], regret=round(st.mean(r['regret'] for r in v), 3), out=round(st.mean(r['out'] for r in v)),
                                refused=sum(r['refused'] for r in v)) for p, v in by_pre.items() if v},
               conf=dict(n=len(conf), mean_p=round(st.mean(p for p, h in conf), 3) if conf else None,
                         hit=round(sum(h for p, h in conf) / len(conf), 3) if conf else None,
                         brier=round(st.mean((p - h) ** 2 for p, h in conf), 3) if conf else None))
    json.dump(out, open(f'{HERE}/{TAG}_analysis.json', 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k not in ('per_pre',)}, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    dict(jobs=jobs, collect=collect, analyze=analyze)[sys.argv[1]]()
