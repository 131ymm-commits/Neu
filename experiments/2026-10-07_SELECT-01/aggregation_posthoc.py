# SELECT-01: какую часть ошибки одной головы снимает голосование (пост-хок 15.10, к вопросу автора о «дельте истины»).
# Для каждой руки: средний регрет одного допустимого голоса против регрета свёртки большинством той же руки (per_task analyze).
# Доля снятой ошибки = 1 − регрет свёртки / регрет голоса. Описательно, вердикт не меняет.
#   python3 aggregation_posthoc.py > aggregation_posthoc.json
import collections, json, os, statistics as st
SEC = {'main': '/root/select_secret', 'rep': '/root/select_secret_rep'}; out = {'note': 'пост-хок, описательно'}
for S in ('main', 'rep'):
    pt = json.load(open(f'{S}_an_wh.json'))['per_task']; votes = collections.defaultdict(list)
    for e in map(json.loads, open(f'evals/{S}_eval.complete.jsonl', encoding='utf-8')):
        if e['task'] in pt and isinstance(e.get('choice'), int) and e['choice'] >= 0:
            tr = json.load(open(f'{SEC[S]}/truth/{e["task"]}.json')); orc, mean = max(tr), st.mean(tr)
            votes[e['arm']].append((orc - tr[e['choice']]) / (orc - mean))
    out[S] = {a: dict(vote_regret=round(st.mean(votes[a]), 3), plurality_regret=round(st.mean(pt[t][a] for t in pt), 3),
                      share_removed=round(1 - st.mean(pt[t][a] for t in pt) / st.mean(votes[a]), 3), votes=len(votes[a]))
              for a in ('B_blind', 'B_zayavka', 'C_N', 'D_N')}
print(json.dumps(out, ensure_ascii=False, indent=1))
