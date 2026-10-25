# PRECOND-01: производные числа PILOT.md (для ledger.py audit). Только арифметика над pilot_analysis.json, планом и голосами SELECT-01.
#   python3 pilot_facts.py  →  pilot_facts.json
import json, math, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); SEL = os.path.join(HERE, '..', '2026-10-07_SELECT-01')
sys.path.insert(0, SEL)
from analyze import a0  # noqa: E402
a = json.load(open(f'{HERE}/pilot_analysis.json')); n = a['n']; sd = a['sd_resid']
se = 2 * sd / math.sqrt(n)                       # разность средних «вкл − выкл» по n/2 голосов в каждой половине
# якоря: голоса C_N (ROLE) и D_N (ROLE_REFUSE) SELECT-01 main на тех же шести задачах; отказ → A0, сбой → 1 — как в пилоте
tasks = sorted({t for t in (json.loads(l)['task'] for l in open(f'{HERE}/evals/pilot.jsonl'))})
votes = {'C_N': [], 'D_N': []}
for e in map(json.loads, open(f'{SEL}/evals/main_eval.jsonl')):
    if e['task'] in tasks and e['arm'] in votes:
        tr = json.load(open(f'/root/select_secret/truth/{e["task"]}.json')); orc, mean = max(tr), st.mean(tr)
        c = e['choice']; reg = lambda i: (orc - tr[i]) / (orc - mean)
        votes[e['arm']].append(reg(c) if isinstance(c, int) and 0 <= c < len(tr) else
                               reg(a0(json.load(open(f'{SEL}/pools/{e["task"]}.json')), e['task'])) if c == -1 else 1.0)
# правда, пересчитанная из опубликованной соли SELECT-01, воспроизводит регрет A0 из main_an_wh.json (ERRORS № 91, поправка)
ref = json.load(open(f'{SEL}/main_an_wh.json'))['per_task']; mism = 0
for t, row in ref.items():
    tr = json.load(open(f'/root/select_secret/truth/{t}.json')); orc, mean = max(tr), st.mean(tr)
    mism += abs((orc - tr[a0(json.load(open(f'{SEL}/pools/{t}.json')), t)]) / (orc - mean) - row['A0']) > 1e-3
pp = a['per_pre']; best = min(pp, key=lambda k: pp[k]['regret']); worst = max(pp, key=lambda k: pp[k]['regret'])
facts = dict(
    se_main_effect=round(se, 3), z={k: round(v['regret'] / se, 1) for k, v in a['effects'].items()},
    n_for_se={str(t): math.ceil((2 * sd / t) ** 2) for t in (0.05, 0.03)},
    anchors={k: dict(votes=len(v), mean_regret=round(st.mean(v), 3)) for k, v in votes.items()}, tasks=tasks,
    best=dict(pre=best, on=pp[best]['on'], regret=pp[best]['regret']), worst=dict(pre=worst, on=pp[worst]['on'], regret=pp[worst]['regret']),
    conf_overconfidence=round(a['conf']['mean_p'] - a['conf']['hit'], 3),
    truth_check=dict(tasks=len(ref), mismatches_A0=mism),
)
json.dump(facts, open(f'{HERE}/pilot_facts.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(facts, ensure_ascii=False))
