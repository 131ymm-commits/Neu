# SELECT-01: числа отчёта, которых нет в выходах analyze / losses / complete — из журналов и per_task (описательно).
#   python3 report_facts.py <выборка: main|rep> > <выборка>_facts.json
import glob, json, statistics as st, sys
from datetime import datetime
S = sys.argv[1]
recs = [json.loads(l) for p in sorted(glob.glob(f'run/{S}_eval_journal/WH_*.jsonl') + glob.glob(f'run/{S}_exec_journal/WH_*.jsonl'))
        for l in open(p, encoding='utf-8')]
fin = [r for r in recs if r.get('final')]
dur = [(datetime.fromisoformat(r['finished']) - datetime.fromisoformat(r['started'])).total_seconds() for r in fin]
log = lambda st_: [json.loads(l) for l in open(f'run/{S}_{st_}_journal/run_log.jsonl', encoding='utf-8') if l.strip()]
started = {st_: sum(1 for e in log(st_) if e.get('event') == 'вызов') for st_ in ('exec', 'eval')}
attempts = {st_: sum(1 for r in recs if (r['arm'] == 'exec') == (st_ == 'exec')) for st_ in ('exec', 'eval')}
an = json.load(open(f'{S}_an_wh.json')); pt = an['per_task']
diffs = {}
for x in ('C_N', 'D_N'):
    d = [pt[t][x] - pt[t]['B_blind'] for t in pt]
    diffs[x] = dict(neg=sum(v < 0 for v in d), zero=sum(v == 0 for v in d), pos=sum(v > 0 for v in d), sd=round(st.stdev(d), 3))
tok = an['tokens']
out = dict(
    first_call=min(r['started'] for r in recs), last_final=max(r['finished'] for r in recs),
    finals=len(fin), finals_exec=sum(r['arm'] == 'exec' for r in fin), finals_eval=sum(r['arm'] != 'exec' for r in fin),
    lost=sum(r['final'] == 'потерян' for r in fin),
    calls_without_record={st_: started[st_] - attempts[st_] for st_ in started},
    limit_waits=sum(1 for r in recs if 'wait_s' in r), na_retries_without_reset=sum(1 for r in recs if r['outcome'] == 'нет ответа' and 'wait_s' not in r),
    out_tokens=sum(r['usage']['out'] for r in fin), inp_tokens=sum(r['usage']['inp'] for r in fin),
    list_cost_usd=round(sum(r['usage']['cost_usd'] or 0 for r in fin), 2),
    call_seconds_median=round(st.median(dur)), call_seconds_max=round(max(dur)),
    versions=sorted({r['cli_init_version'] for r in fin}), models=sorted({m for r in fin for m in r['model_usage_keys']}),
    efforts=sorted({r['effort'] for r in fin}), init_variants=sorted({r['init_sha256'][:8] for r in fin}),
    per_task_diff_vs_B_blind=diffs,
    D_N_equal_A0_tasks=sum(pt[t]['D_N'] == pt[t]['A0'] for t in pt),
    D_N_over_C_N_out_pct=round(100 * (tok['D_N']['out'] / tok['C_N']['out'] - 1)),
)
print(json.dumps(out, ensure_ascii=False, indent=1))
