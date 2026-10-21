# THINK-01: производные числа отчёта по основной выборке (для ledger.py audit). Только арифметика над main_an.json и журналами.
#   python3 report_facts_think.py main  →  main_facts.json
import json, sys, glob, hashlib, subprocess
from datetime import datetime
S = sys.argv[1]; a = json.load(open(f'{S}_an.json')); p = a['primary']; tok = a['tokens_per_task']; MC = 200000
le = {k: round(v['p'] * (MC + 1) - 1, 3) for k, v in p.items()}            # число перестановок с разностью ≤ наблюдаемой
starts = [json.loads(l).get('started', '') for f in glob.glob(f'run/{S}_eval_*_journal/WH_*.jsonl') for l in open(f, encoding='utf-8')]
ev = json.load(open(f'{S}_push_activity.json'))['event']
# совет 35: пауза — по run_log (поле at): самый длинный промежуток между соседними записями каждой ветки; последнее «готово»
logs = {b: [json.loads(l) for l in open(f'run/{S}_eval_{b}_journal/run_log.jsonl', encoding='utf-8')] for b in ('high', 'medium')}
def gap(r):
    x, y = max(zip(r, r[1:]), key=lambda xy: datetime.fromisoformat(xy[1]['at']) - datetime.fromisoformat(xy[0]['at']))
    return dict(from_at=x['at'], from_event=x['event'], from_reason=x.get('причина'), to_at=y['at'], to_event=y['event'])
git = lambda *c: subprocess.run(['git', *c], capture_output=True, check=True).stdout
commit_at = git('show', '-s', '--format=%cI', ev['after']).decode().strip()
facts = dict(
    perm_le=le, p_floor=round(1 / (MC + 1), 9),
    out_ratio_B_blind=round(tok['B_blind']['out'] / tok['H_1']['out'], 2), out_ratio_D_N=round(tok['D_N']['out'] / tok['H_1']['out'], 2),
    out_ratio_H_c=round(tok['H_c']['out'] / tok['H_1']['out'], 2),
    regret_ratio_B_blind=round(a['mean_regret']['B_blind']['mean'] / a['mean_regret']['H_1']['mean'], 2),
    first_start=min(s for s in starts if s), last_start=max(starts), push_time=ev['timestamp'], push_after=ev['after'][:7],
    s3_overconfidence=round(a['secondary']['S3_self_assessment']['mean_p_best'] - a['secondary']['S3_self_assessment']['accuracy_lenient'], 3),
    s3_gap_strict=round(a['secondary']['S3_self_assessment']['accuracy_strict'] - a['secondary']['S3_self_assessment']['mean_p_best'], 3),
    # совет 35: доли задач с регретом 0 и > 0,5; запас выхода H_1 над свёртками S1b и пост-хок поправка по наклону S2
    zero_and_bad={arm: [sum(1 for t in a['per_task'].values() if t[arm] == 0), sum(1 for t in a['per_task'].values() if t[arm] > 0.5)]
                  for arm in ('H_1', 'H_c', 'D_N', 'B_blind')},
    s1b_margin={k: dict(extra_out=round(v['out_H_1'] / v['out_subset'] - 1, 3),
                        slope_correction=round(-a['secondary']['S2_mechanism']['equal_length_model']['ln_out']['coef'] * __import__('math').log(v['out_H_1'] / v['out_subset']), 3))
                for k, v in a['secondary']['S1b_equal_budget_system'].items() if k != 'curve_m_1_5'},
    pause={b: gap(r) for b, r in logs.items()}, last_done={b: max(x['at'] for x in r if x['event'] == 'готово') for b, r in logs.items()},
    # хеш файла выборов внутри коммита до правды и на диске; время коммита и его запас до серверного события пуша
    eval_sha_in_commit=hashlib.sha256(git('show', f"{ev['after']}:./evals/{S}_eval.jsonl")).hexdigest(),
    eval_sha_on_disk=hashlib.sha256(open(f'evals/{S}_eval.jsonl', 'rb').read()).hexdigest(),
    commit_at=commit_at, commit_before_push_s=int((datetime.fromisoformat(ev['timestamp'].replace('Z', '+00:00')) - datetime.fromisoformat(commit_at)).total_seconds()),
)
json.dump(facts, open(f'{S}_facts.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(facts, ensure_ascii=False))
