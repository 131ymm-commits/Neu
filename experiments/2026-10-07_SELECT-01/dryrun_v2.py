# SELECT-01: сухой прогон цепочки run_sealed2 → export → harness.py collect_eval на записях пилота 2, без голов.
#   python3 dryrun_v2.py <папка-песочница>
# Заглушка вызова отдаёт поток, собранный из записи пилота 2: годная запись → годный поток с тем же ответом и токенами;
# запись, оборванная лимитом, → сначала итог лимита (rate_limit_event со статусом rejected), затем годный поток с выбором 0.
# Проверки: (1) годные записи пилота 2 дают в evals тот же choice, inp, out; (2) 38 записей лимита дают по одному
# ожиданию сброса и не дают «потерян»; (3) порядок вызовов — задача за задачей, руки вперемешку; (4) этап исполнителя:
# collect_exec по выгрузке v2 даёт те же sha256 пулов, что записаны в run/p2_exec_pools.sha256; (5) complete.py,
# losses.py (обе ветки, на синтетических потерях) и pool.py исполняются и дают ожидаемое (совет 31).
import json, os, shutil, subprocess, sys
from datetime import datetime, timedelta, timezone
here = os.path.dirname(os.path.abspath(__file__)); repo = os.path.abspath(os.path.join(here, '..', '..'))
sys.path.insert(0, os.path.join(repo, 'tools'))
import run_sealed2 as rs  # noqa: E402

box = os.path.abspath(sys.argv[1]); shutil.rmtree(box, ignore_errors=True); os.makedirs(box)
for d in ('tasks', 'pools'):
    shutil.copytree(os.path.join(here, d), os.path.join(box, d))
os.makedirs(os.path.join(box, 'run')); os.makedirs(os.path.join(box, 'evals'))
for f in ('seeds_pilot2.json', 'run/p2_eval_out.jsonl'):
    shutil.copy(os.path.join(here, f), os.path.join(box, f))
v1 = {r['id']: r for r in map(json.loads, open(os.path.join(here, 'run', 'p2_eval_out.jsonl')))}
jobs = rs.load_jobs(os.path.join(here, 'run', 'p2_eval_jobs.jsonl'), task_from_id=True)
assert len(jobs) == len(v1) == 324, (len(jobs), len(v1))

T = [datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc)]
calls, seen_limit = [], set()


def stream(r):
    u = dict(input_tokens=r['inp'], cache_creation_input_tokens=0, cache_read_input_tokens=0, output_tokens=r['out'],
             output_tokens_details=dict(thinking_tokens=r.get('thinking') or 0))
    return [dict(type='system', subtype='init', claude_code_version=rs.PINNED_VERSION, model='claude-opus-5-5'),
            dict(type='stream_event', event=dict(type='message_start', message=dict(model='claude-opus-5-5'))),
            dict(type='stream_event', event=dict(type='message_delta', delta=dict(stop_reason='tool_use'))),
            dict(type='stream_event', event=dict(type='message_stop')),
            dict(type='result', subtype='success', is_error=False, result='', structured_output=r['result'],
                 total_cost_usd=r.get('cost_usd') or 0.01, usage=u, permission_denials=[],
                 modelUsage={'claude-opus-5-5': dict(outputTokens=r['out'])})]


def fake_call(cfg, job, gz):
    calls.append(job['id']); r = v1[job['id']]
    if r.get('error') and job['id'] not in seen_limit:
        seen_limit.add(job['id'])
        reset = T[0] + timedelta(hours=1)
        ev = [dict(type='system', subtype='init', claude_code_version=rs.PINNED_VERSION),
              dict(type='rate_limit_event', rate_limit_info=dict(status='rejected', resetsAt=reset.timestamp())),
              dict(type='result', subtype='success', is_error=True, result=r['error'].split(': ', 1)[-1],
                   structured_output=None, total_cost_usd=0, modelUsage={}, permission_denials=[],
                   usage=dict(input_tokens=0, cache_creation_input_tokens=0, cache_read_input_tokens=0, output_tokens=0))]
    elif r.get('error'):
        ev = stream(dict(result={'choice': 0}, inp=5000, out=1000))
    else:
        ev = stream(r)
    return rs.CallResult(events=ev, started=T[0], finished=T[0], returncode=0)


def sleep(s):
    T[0] += timedelta(seconds=s)


drv = rs.Driver(rs.default_config(), seed='dryrun-v2', jobs_sha256='dryrun', journal_dir=os.path.join(box, 'journal'),
                streams_dir=os.path.join(box, 'streams'), call_fn=fake_call, pre_call_check=lambda: rs.PINNED_BIN_SHA256,
                now_fn=lambda: T[0], sleep_fn=sleep, log=lambda m: None)
drv.start(); drv.run(jobs)
rs.cmd_export(type('A', (), dict(journal=os.path.join(box, 'journal'), out=os.path.join(box, 'run', 'p2v2_eval_out.jsonl'))))

env = dict(os.environ, SELECT_ROOT=box)
for stage in ('p2_eval', 'p2v2_eval'):
    subprocess.run([sys.executable, os.path.join(here, 'harness.py'), 'collect_eval', stage], env=env, check=True)
old = {(e['task'], e['arm'], e['i']): e for e in map(json.loads, open(os.path.join(box, 'evals', 'p2_eval.jsonl')))}
new = {(e['task'], e['arm'], e['i']): e for e in map(json.loads, open(os.path.join(box, 'evals', 'p2v2_eval.jsonl')))}
assert set(old) == set(new), 'наборы (задача, рука, i) разные'
same = sum(1 for k, e in old.items() if not e['error'] and all(new[k][f] == e[f] for f in ('choice', 'shown_choice', 'inp', 'out')))
ok_old = sum(1 for e in old.values() if not e['error'])
lost = sum(1 for e in new.values() if e['error'])
recs = list(rs.journal_records(os.path.join(box, 'journal')))
waits = sum(1 for r in recs if r['outcome'] == rs.NA and 'wait_s' in r)
order_tasks = [c.split('|')[0] for c in calls]
blocks = [t for i, t in enumerate(order_tasks) if i == 0 or t != order_tasks[i - 1]]
arms_first = [c.split('|')[1] for c in calls[:27]]
print(f'годных записей пилота 2: {ok_old}; совпали в evals (choice, inp, out): {same}')
print(f'ожиданий сброса: {waits}; «потерян»: {lost}; вызовов: {len(calls)}; блоков задач подряд: {len(blocks)}')
print('руки первых 27 вызовов:', ' '.join(arms_first))
assert same == ok_old == 286 and waits == 38 and lost == 0 and len(calls) == 324 + 38 and len(blocks) == 12

# этап исполнителя: те же записи пилота 2 → журнал v2 → export → collect_exec → те же хеши пулов
v1x = {r['id']: r for r in map(json.loads, open(os.path.join(here, 'run', 'p2_exec_out.jsonl')))}
xjobs = rs.load_jobs(os.path.join(here, 'run', 'p2_exec_jobs.jsonl'), task_from_id=True)
v1.update(v1x)
drv = rs.Driver(rs.default_config(), seed='dryrun-v2-exec', jobs_sha256='dryrun', journal_dir=os.path.join(box, 'journal_exec'),
                streams_dir=os.path.join(box, 'streams'), call_fn=fake_call, pre_call_check=lambda: rs.PINNED_BIN_SHA256,
                now_fn=lambda: T[0], sleep_fn=sleep, log=lambda m: None)
drv.start(); drv.run(xjobs)
rs.cmd_export(type('A', (), dict(journal=os.path.join(box, 'journal_exec'), out=os.path.join(box, 'run', 'p2v2_exec_out.jsonl'))))
shutil.rmtree(os.path.join(box, 'pools')); os.makedirs(os.path.join(box, 'pools'))
subprocess.run([sys.executable, os.path.join(here, 'harness.py'), 'collect_exec', 'p2v2_exec'], env=env, check=True)
want = json.load(open(os.path.join(here, 'run', 'p2_exec_pools.sha256')))
got = json.load(open(os.path.join(box, 'run', 'p2v2_exec_pools.sha256')))
print(f'пулов пилота 2: {len(want)}; совпали по sha256: {sum(got.get(t) == h for t, h in want.items())}')
assert got == want

# полнота (complete.py): 12 полных задач; затем у WH_7305 убираются две записи → задача неполная и исключается
def run_json(args):
    r = subprocess.run([sys.executable] + args, env=env, capture_output=True, text=True, check=True)
    return json.loads(r.stdout)
c = run_json([os.path.join(here, 'complete.py'), 'p2v2_eval', 'seeds_pilot2.json', 'WH'])
assert c['complete'] == 12 and not c['incomplete'] and not c['no_pool'], c
ev = os.path.join(box, 'evals', 'p2v2_eval.jsonl'); keep = open(ev).read().splitlines(True)
cut = [l for l in keep if json.loads(l)['task'] == 'WH_7305'][:2]
open(ev, 'w').writelines([l for l in keep if l not in cut])
c = run_json([os.path.join(here, 'complete.py'), 'p2v2_eval', 'seeds_pilot2.json', 'WH'])
assert c['complete'] == 11 and c['incomplete'] == {'WH_7305': 25}, c
open(ev, 'w').writelines(keep)
print(f"полнота: 12 полных задач; без двух записей WH_7305 — 11 полных, неполная {c['incomplete']}")

# правило потерь (losses.py) на синтетике: у C_N два «потерян», у B_blind один, у D_N три попытки «нет ответа» до начала
jl = os.path.join(box, 'journal_losses'); shutil.copytree(os.path.join(box, 'journal'), jl)
for f in sorted(os.listdir(jl)):
    if not f.startswith('WH_'):
        continue
    out = []
    for line in open(os.path.join(jl, f)):
        r = json.loads(line)
        if r.get('final') == 'годный' and (r['job'] in ('WH_7302|C_N|1', 'WH_7303|C_N|1', 'WH_7303|B_blind|2')):
            r.update(final='потерян', outcome=rs.FAIL, reason='нет structured_output (синтетика)')
        out.append(json.dumps(r, ensure_ascii=False))
        if r['job'] in ('WH_7304|D_N|0', 'WH_7304|D_N|1', 'WH_7306|D_N|2') and r.get('final'):
            na = dict(r, outcome=rs.NA, final=None, reason='таймаут или гибель до message_start (синтетика)')
            out.insert(len(out) - 1, json.dumps(na, ensure_ascii=False))
    open(os.path.join(jl, f), 'w').write('\n'.join(out) + '\n')
L = run_json([os.path.join(here, 'losses.py'), jl, ev])
assert L['rule']['C_N']['not_measured'] is True and L['rule']['D_N']['not_measured'] is True, L['rule']
assert L['by_arm']['C_N']['потерян'] == 2 and L['by_arm']['D_N']['нет_ответа_до_начала'] == 3, L['by_arm']
assert L['secondary']['C_N']['excluded_tasks'] == ['WH_7302', 'WH_7303'] and L['secondary']['C_N']['n_tasks'] == 10, L['secondary']
assert L['secondary']['D_N']['excluded_tasks'] == ['WH_7303'] and L['secondary']['D_N']['n_tasks'] == 11, L['secondary']
print('правило потерь: C_N — «не измерено» по доле «потерян», D_N — по доле «нет ответа» до начала; вторичный анализ без задач с потерями прошёл')

# объединённая оценка (pool.py): пилот 1 и пилот 2 — непересекающиеся задачи
P = run_json([os.path.join(here, 'pool.py'), os.path.join(here, 'pilot_an_wh.json'), os.path.join(here, 'p2_an_wh.json')])
assert P['n_tasks'] == [12, 12] and P['pooled']['D_N − B_blind']['n'] == 24, P
print('объединение:', {k: (v['mean'], v['ci95']) for k, v in P['pooled'].items()})
print('сухой прогон: всё сошлось')
