# SELECT-01: разнообразие промптов как источник независимых ошибок (пост-хок 15.10, к «дельте истины»). Описательно.
# 1) Пары голосов одной задачи: доля пар, выбравших одного кандидата, и доля пар с одинаковой ОШИБКОЙ (оба выбрали одного
#    не лучшего), — внутри руки и между руками.
# 2) Свёртки равного числа голосов: одна рука против смеси рук (состав задан до расчёта):
#    5 голосов: C_N×5 | D_N×5 | смесь C_N[0:2]+D_N[0:2]+B_blind[0:1]
#    12 голосов: B_blind×12 | смесь B_blind[0:4]+C_N[0:4]+D_N[0:4]
#    все 27 голосов (B_blind 12, B_zayavka 5, C_N 5, D_N 5).
#    Доля снятой ошибки = 1 − регрет свёртки / средний регрет её голосов. Ничьи — sha256(задача|кандидат), как в SELECT-01.
#   python3 diversity_posthoc.py > diversity_posthoc.json
import collections, itertools, json, statistics as st, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import plurality  # noqa: E402
SEC = {'main': '/root/select_secret', 'rep': '/root/select_secret_rep'}; out = {'note': 'пост-хок, описательно; отказы D_N (−1) — не голос'}
MIX = {'5: C_N×5': [('C_N', 5)], '5: D_N×5': [('D_N', 5)], '5: C_N2+D_N2+B_blind1': [('C_N', 2), ('D_N', 2), ('B_blind', 1)],
       '12: B_blind×12': [('B_blind', 12)], '12: B_blind4+C_N4+D_N4': [('B_blind', 4), ('C_N', 4), ('D_N', 4)],
       '27: все руки': [('B_blind', 12), ('B_zayavka', 5), ('C_N', 5), ('D_N', 5)]}
for S in ('main', 'rep'):
    pt = json.load(open(f'{S}_an_wh.json'))['per_task']; V = collections.defaultdict(dict)
    for e in map(json.loads, open(f'evals/{S}_eval.complete.jsonl', encoding='utf-8')):
        if e['task'] in pt: V[(e['task'], e['arm'])][int(e['i'])] = e.get('choice')
    pairs = collections.defaultdict(lambda: [0, 0, 0]); fold = collections.defaultdict(list); single = collections.defaultdict(list)
    for t in sorted(pt):
        tr = json.load(open(f'{SEC[S]}/truth/{t}.json')); orc, mean = max(tr), st.mean(tr); best = {i for i, v in enumerate(tr) if v == orc}
        reg = lambda i: (orc - tr[i]) / (orc - mean)
        valid = lambda c: isinstance(c, int) and 0 <= c < len(tr)
        votes = [(a, c) for a in ('B_blind', 'B_zayavka', 'C_N', 'D_N') for i, c in sorted(V[(t, a)].items()) if valid(c)]
        for (a1, c1), (a2, c2) in itertools.combinations(votes, 2):
            key = 'внутри руки' if a1 == a2 else 'между руками'
            p = pairs[key]; p[0] += 1; p[1] += c1 == c2; p[2] += (c1 == c2 and c1 not in best)
            p = pairs[' – '.join(sorted((a1, a2)))]; p[0] += 1; p[1] += c1 == c2; p[2] += (c1 == c2 and c1 not in best)
        for name, comp in MIX.items():
            vs = [V[(t, a)][i] for a, n in comp for i in range(n) if valid(V[(t, a)].get(i))]
            if vs:
                fold[name].append(reg(plurality(vs, t))); single[name].append(st.mean(reg(c) for c in vs))
    out[S] = dict(pairs={k: dict(pairs=v[0], same_choice=round(v[1] / v[0], 3), same_error=round(v[2] / v[0], 3)) for k, v in sorted(pairs.items())},
                  folds={k: dict(fold_regret=round(st.mean(fold[k]), 3), mean_vote_regret=round(st.mean(single[k]), 3),
                                 share_removed=round(1 - st.mean(fold[k]) / st.mean(single[k]), 3), tasks=len(fold[k])) for k in MIX})
print(json.dumps(out, ensure_ascii=False, indent=1))
