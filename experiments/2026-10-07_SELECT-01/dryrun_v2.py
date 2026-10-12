# SELECT-01: сухой прогон цепочки run_sealed2 → export → harness.py collect_eval на записях пилота 2, без голов.
#   python3 dryrun_v2.py <папка-песочница>
# Заглушка вызова отдаёт поток, собранный из записи пилота 2: годная запись → годный поток с тем же ответом и токенами;
# запись, оборванная лимитом, → сначала итог лимита (rate_limit_event со статусом rejected), затем годный поток с выбором 0.
# Проверки: (1) годные записи пилота 2 дают в evals тот же choice, inp, out; (2) 38 записей лимита дают по одному
# ожиданию сброса и не дают «потерян»; (3) порядок вызовов — задача за задачей, руки вперемешку; (4) analyze.py проходит.
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
print('сухой прогон: всё сошлось')
