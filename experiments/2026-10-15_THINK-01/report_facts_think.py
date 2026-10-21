# THINK-01: производные числа отчёта по основной выборке (для ledger.py audit). Только арифметика над main_an.json и журналами.
#   python3 report_facts_think.py main  →  main_facts.json
import json, sys, glob
S = sys.argv[1]; a = json.load(open(f'{S}_an.json')); p = a['primary']; tok = a['tokens_per_task']; MC = 200000
le = {k: round(v['p'] * (MC + 1) - 1, 3) for k, v in p.items()}            # число перестановок с разностью ≤ наблюдаемой
starts = [json.loads(l).get('started', '') for f in glob.glob(f'run/{S}_eval_*_journal/WH_*.jsonl') for l in open(f, encoding='utf-8')]
ev = json.load(open(f'{S}_push_activity.json'))['event']
facts = dict(
    perm_le=le, p_floor=round(1 / (MC + 1), 9),
    out_ratio_B_blind=round(tok['B_blind']['out'] / tok['H_1']['out'], 2), out_ratio_D_N=round(tok['D_N']['out'] / tok['H_1']['out'], 2),
    out_ratio_H_c=round(tok['H_c']['out'] / tok['H_1']['out'], 2),
    regret_ratio_B_blind=round(a['mean_regret']['B_blind']['mean'] / a['mean_regret']['H_1']['mean'], 2),
    first_start=min(s for s in starts if s), last_start=max(starts), push_time=ev['timestamp'], push_after=ev['after'][:7],
    s3_overconfidence=round(a['secondary']['S3_self_assessment']['mean_p_best'] - a['secondary']['S3_self_assessment']['accuracy_lenient'], 3),
)
json.dump(facts, open(f'{S}_facts.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(facts, ensure_ascii=False))
