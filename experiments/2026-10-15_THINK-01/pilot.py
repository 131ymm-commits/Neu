# THINK-01, пилот (ворота 1 CLAUDE.md; до PREREG): задачи — первые 6 задач основной выборки SELECT-01 (WH_8001–8006),
# в тест THINK-01 они не войдут. Пулы, порядок кандидатов (perm) и правда — из SELECT-01; там же уже есть голоса
# C_N и D_N на effort medium (5 и 5 на задачу). Новые руки пилота, по 5 вызовов:
#   C_N@high (ROLE, effort high), U_N@medium (ROLE_UNSURE), P_N@medium (ROLE_PLACEBO).
#   python3 pilot.py jobs      — run/pilot_high_jobs.jsonl (C_N) и run/pilot_medium_jobs.jsonl (U_N, P_N)
#   python3 pilot.py collect   — evals/pilot.jsonl из выгрузок run/pilot_{high,medium}_out.jsonl (выбор — в номерах пула)
#   python3 pilot.py analyze   — длина (выход) и регрет по рукам, вместе с голосами SELECT-01 на тех же задачах
import collections, json, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); SEL = os.path.join(HERE, '..', '2026-10-07_SELECT-01')
sys.path.insert(0, SEL); sys.path.insert(0, HERE)
import harness as H, prompts as P, sim, prompts_think as PT  # noqa: E402
TASKS = [f'WH_{s}' for s in range(8001, 8007)]
RUNS = dict(high=dict(C_N=5), medium=dict(U_N=5, P_N=5))

def jobs():
    for run, spec in RUNS.items():
        js = []
        for t in TASKS:
            tk = H.task(t); pool = json.load(open(f'{SEL}/pools/{t}.json')); shown = [pool[j] for j in H.perm(t)]; rules = sim.RULES[tk['type']](tk)
            for a, n in spec.items():
                js += [dict(id=f'{t}|{a}@{run}|{i}', prompt=PT.eval_prompt(a, rules, shown), schema=P.EVAL_SCHEMA) for i in range(n)]
        p = f'{HERE}/run/pilot_{run}_jobs.jsonl'
        with open(p, 'w') as fh:
            for j in js: fh.write(json.dumps(j, ensure_ascii=False) + '\n')
        print(p, len(js))

def collect():
    os.makedirs(f'{HERE}/evals', exist_ok=True); n = 0
    with open(f'{HERE}/evals/pilot.jsonl', 'w') as fh:
        for run in RUNS:
            for r in map(json.loads, open(f'{HERE}/run/pilot_{run}_out.jsonl')):
                t, a, i = r['id'].split('|'); pm = H.perm(t); c = (r.get('result') or {}).get('choice')
                ch = None if r.get('error') else (pm[c] if isinstance(c, int) and 0 <= c < len(pm) else c)
                fh.write(json.dumps(dict(task=t, arm=a, i=int(i), choice=ch, shown_choice=c, error=r.get('error'), inp=r.get('inp', 0),
                                         out=r.get('out', 0)), ensure_ascii=False) + '\n'); n += 1
    print(n, 'выборов')

def analyze():
    sec = os.environ.get('SELECT_SECRET', '/root/select_secret'); V = collections.defaultdict(list)
    for f, tag in ((f'{SEL}/evals/main_eval.complete.jsonl', '@medium'), (f'{HERE}/evals/pilot.jsonl', '')):
        for e in map(json.loads, open(f)):
            if e['task'] in TASKS and (tag == '' or e['arm'] in ('C_N', 'D_N', 'B_blind')):
                V[e['arm'] + tag].append(e)
    out = {}; per_task = collections.defaultdict(dict)
    for arm, es in sorted(V.items()):
        reg, ln, ref = [], [], 0; by_t = collections.defaultdict(list)
        for e in es:
            tr = json.load(open(f'{sec}/truth/{e["task"]}.json')); orc, mean = max(tr), st.mean(tr)
            if e['choice'] == -1: ref += 1; continue
            if isinstance(e['choice'], int) and 0 <= e['choice'] < len(tr):
                reg.append((orc - tr[e['choice']]) / (orc - mean)); ln.append(e['out']); by_t[e['task']].append(reg[-1])
        out[arm] = dict(votes=len(es), answered=len(reg), refusals=ref, mean_vote_regret=round(st.mean(reg), 3),
                        mean_out=round(st.mean(ln)), median_out=round(st.median(ln)), sum_out_per_task=round(sum(ln) / len(TASKS)))
        for t, v in by_t.items(): per_task[t][arm] = round(st.mean(v), 3)
    print(json.dumps(dict(note='пилот THINK-01: 6 задач SELECT-01 main; голоса @medium без пометки пилота — из SELECT-01', arms=out, per_task_mean_vote_regret=dict(sorted(per_task.items()))), ensure_ascii=False, indent=1))

if __name__ == '__main__':
    dict(jobs=jobs, collect=collect, analyze=analyze)[sys.argv[1]]()
