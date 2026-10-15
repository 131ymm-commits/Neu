# DIVERSE-01, пилот (до PREREG): снимают ли голоса РАЗНЫХ моделей больше ошибки, чем копии одной (вопрос «дельты истины», 15.10).
# Задачи — WH_8001–8006 (SELECT-01 main; те же, что в пилоте THINK-01). Промпт — C_N (ROLE) SELECT-01 байт в байт, effort medium.
# Новые голоса: Sonnet 5.5, Haiku 5.5, Fable 5.1 — по 5 на задачу (конфиги run/div_<модель>.json). Голоса Opus 5.5 на medium —
# из SELECT-01 (C_N, 5 на задачу). Правда — SELECT-01.
#   python3 pilot_div.py jobs | collect | analyze
import collections, itertools, json, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); SEL = os.path.join(HERE, '..', '2026-10-07_SELECT-01')
sys.path.insert(0, SEL)
import harness as H, prompts as P, sim  # noqa: E402
from analyze import plurality  # noqa: E402
TASKS = [f'WH_{s}' for s in range(8001, 8007)]; MODELS = ('sonnet', 'haiku', 'fable'); N = 5

def jobs():
    for m in MODELS:
        js = []
        for t in TASKS:
            tk = H.task(t); pool = json.load(open(f'{SEL}/pools/{t}.json')); shown = [pool[j] for j in H.perm(t)]
            js += [dict(id=f'{t}|C_N@{m}|{i}', prompt=P.eval_prompt('C_N', sim.RULES[tk['type']](tk), shown), schema=P.EVAL_SCHEMA) for i in range(N)]
        with open(f'{HERE}/run/pilot_{m}_jobs.jsonl', 'w') as fh:
            for j in js: fh.write(json.dumps(j, ensure_ascii=False) + '\n')
        print(m, len(js))

def collect():
    os.makedirs(f'{HERE}/evals', exist_ok=True); n = 0
    with open(f'{HERE}/evals/pilot.jsonl', 'w') as fh:
        for m in MODELS:
            p = f'{HERE}/run/pilot_{m}_out.jsonl'
            if not os.path.exists(p): continue
            for r in map(json.loads, open(p)):
                t, a, i = r['id'].split('|'); pm = H.perm(t); c = (r.get('result') or {}).get('choice')
                ch = None if r.get('error') else (pm[c] if isinstance(c, int) and 0 <= c < len(pm) else c)
                fh.write(json.dumps(dict(task=t, arm=a, i=int(i), choice=ch, error=r.get('error'), out=r.get('out', 0), models=r.get('models')), ensure_ascii=False) + '\n'); n += 1
    print(n, 'выборов')

def analyze():
    sec = '/root/select_secret'; V = collections.defaultdict(dict); outs = collections.defaultdict(list)
    for e in map(json.loads, open(f'{SEL}/evals/main_eval.complete.jsonl')):
        if e['task'] in TASKS and e['arm'] == 'C_N': V[(e['task'], 'opus')][e['i']] = e['choice']; outs['opus'].append(e['out'])
    for e in map(json.loads, open(f'{HERE}/evals/pilot.jsonl')):
        m = e['arm'].split('@')[1]; V[(e['task'], m)][e['i']] = e['choice']; outs[m].append(e.get('out', 0))
    ms = ('opus',) + MODELS
    MIX = {f'5: {m}×5': [(m, 5)] for m in ms}
    MIX.update({'5: opus2+sonnet1+haiku1+fable1': [('opus', 2), ('sonnet', 1), ('haiku', 1), ('fable', 1)],
                '20: все четыре ×5': [(m, 5) for m in ms], '15: opus+sonnet+fable ×5': [('opus', 5), ('sonnet', 5), ('fable', 5)]})
    vote = collections.defaultdict(list); pairs = collections.defaultdict(lambda: [0, 0, 0]); fold = collections.defaultdict(list); single = collections.defaultdict(list)
    per_task = collections.defaultdict(dict)
    for t in TASKS:
        tr = json.load(open(f'{sec}/truth/{t}.json')); orc, mean = max(tr), st.mean(tr); best = {i for i, v in enumerate(tr) if v == orc}
        reg = lambda i: (orc - tr[i]) / (orc - mean); valid = lambda c: isinstance(c, int) and 0 <= c < len(tr)
        vs = [(m, c) for m in ms for i, c in sorted(V[(t, m)].items()) if valid(c)]
        for m, c in vs: vote[m].append(reg(c))
        for m in ms:
            v = [reg(c) for mm, c in vs if mm == m]
            if v: per_task[t][m] = round(st.mean(v), 3)
        for (m1, c1), (m2, c2) in itertools.combinations(vs, 2):
            for key in ('внутри модели' if m1 == m2 else 'между моделями', ' – '.join(sorted((m1, m2)))):
                p = pairs[key]; p[0] += 1; p[1] += c1 == c2; p[2] += (c1 == c2 and c1 not in best)
        for name, comp in MIX.items():
            cs = [V[(t, m)][i] for m, n in comp for i in range(n) if valid(V[(t, m)].get(i))]
            if cs: fold[name].append(reg(plurality(cs, t))); single[name].append(st.mean(reg(c) for c in cs))
    out = dict(note='пилот DIVERSE-01: 6 задач SELECT-01 main; opus — голоса C_N SELECT-01 (medium)',
               per_model={m: dict(votes=len(vote[m]), mean_vote_regret=round(st.mean(vote[m]), 3), mean_out=round(st.mean(outs[m])) if outs[m] else None) for m in ms if vote[m]},
               pairs={k: dict(pairs=v[0], same_choice=round(v[1] / v[0], 3), same_error=round(v[2] / v[0], 3)) for k, v in sorted(pairs.items())},
               folds={k: dict(fold_regret=round(st.mean(fold[k]), 3), mean_vote_regret=round(st.mean(single[k]), 3),
                              share_removed=round(1 - st.mean(fold[k]) / st.mean(single[k]), 3) if st.mean(single[k]) else None) for k in MIX if fold[k]},
               per_task_vote_regret=dict(per_task))
    print(json.dumps(out, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    dict(jobs=jobs, collect=collect, analyze=analyze)[sys.argv[1]]()
