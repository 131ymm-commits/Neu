# SELECT-01: вторичные описательные числа ПОСЛЕ результата (совет 32, «что проверить первым», п. 2). Вывода не дают, p нет.
#   SELECT_SECRET=<соль выборки> python3 report_secondary.py <выборка: main|rep> > <выборка>_secondary.json
# 1) D_N − B_blind по задачам: с отказом D_N (хоть один choice = −1) и без; без 5 самых отрицательных задач.
# 2) D_N − C_N и D − C: среднее и 95 % ДИ бутстрепом по задачам (analyze.boot_ci) — знаки для критерия специфичности.
# 3) Позиции: где в показанном порядке стоял лучший по правде кандидат и какие позиции выбирали руки
#    (порядок — одна перестановка на задачу, общая для всех рук: harness.perm).
import collections, json, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import boot_ci  # noqa: E402
from harness import perm  # noqa: E402
S = sys.argv[1]; SEC = os.environ.get('SELECT_SECRET', '/root/select_secret')
pt = json.load(open(f'{S}_an_wh.json'))['per_task']
ev = [json.loads(l) for l in open(f'evals/{S}_eval.complete.jsonl', encoding='utf-8')]
refused = {e['task'] for e in ev if e['arm'] == 'D_N' and e.get('choice') == -1}
d = {t: pt[t]['D_N'] - pt[t]['B_blind'] for t in pt}
grp = lambda ts: dict(n=len(ts), mean=round(st.mean(d[t] for t in ts), 3)) if ts else dict(n=0)
trim = sorted(d.values())[5:]
pair = lambda x, y: [pt[t][x] - pt[t][y] for t in sorted(pt)]
ci = lambda v: [round(a, 3) for a in boot_ci(v)]
best_pos = collections.Counter()
choice_pos = collections.defaultdict(collections.Counter)
for t in sorted(pt):
    truth = json.load(open(f'{SEC}/truth/{t}.json')); pm = perm(t)
    best = max(range(len(truth)), key=lambda i: truth[i])
    best_pos[pm.index(best)] += 1
for e in ev:
    if e['task'] in pt and isinstance(e.get('shown_choice'), int) and e['shown_choice'] >= 0:
        choice_pos[e['arm']][e['shown_choice']] += 1
out = dict(
    note='описательно, после результата; вывода не дают',
    D_N_minus_B_blind=dict(all=grp(sorted(d)), tasks_with_D_N_refusal=grp(sorted(refused & set(d))),
                           tasks_without_D_N_refusal=grp(sorted(set(d) - refused)),
                           without_5_most_negative=dict(n=len(trim), mean=round(st.mean(trim), 3))),
    D_N_refusals=dict(votes=sum(1 for e in ev if e['arm'] == 'D_N' and e.get('choice') == -1), tasks=len(refused)),
    D_N_minus_C_N=dict(mean=round(st.mean(pair('D_N', 'C_N')), 3), ci95=ci(pair('D_N', 'C_N'))),
    D_minus_C=dict(mean=round(st.mean(pair('D', 'C')), 3), ci95=ci(pair('D', 'C'))),
    truth_best_shown_position={str(k): best_pos[k] for k in sorted(best_pos)},
    choice_shown_position={a: {str(k): c[k] for k in sorted(c)} for a, c in sorted(choice_pos.items())},
)
print(json.dumps(out, ensure_ascii=False, indent=1))
