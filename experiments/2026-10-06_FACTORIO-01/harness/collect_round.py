# Сбор раунда: финальная мера всех слотов (демон, мера ред. 2) + ответы голов из workflow → rounds/<name>.json
#   python3 collect_round.py <name> <run_id> <n_slots>
import json, subprocess, sys, os
from concurrent.futures import ThreadPoolExecutor
name, run_id, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
W = f'/root/.claude/projects/-home-user/368a3030-ed6f-5d75-8ccd-d3417f8f1866/workflows/{run_id}.json'
res = json.load(open(W))['result']; res = json.loads(res) if isinstance(res, str) else res; out = res['out']
ids = list(out.keys())
def logged_final(k):
    # итог из лога демона (демон после финала завершается; сбор после сбоя не мерит повторно)
    _, label, task = ids[k].split('|'); p = f'/tmp/claude-0/fact/logs/{name}_{label}_{task}.jsonl'
    if os.path.exists(p):
        for line in reversed(open(p).read().splitlines()):
            d = json.loads(line)
            if d.get('event') == 'final': return {kk: d[kk] for kk in ('final', 'measure', 'success', 'best_during', 'steps')}
    return None
def fin(k):
    f = logged_final(k)
    if f: return f
    try: return json.loads(subprocess.run(['python3', 'fle_step.py', str(k), 'final'], capture_output=True, text=True, timeout=1800).stdout)
    except Exception as e: return dict(lost=True, error=str(e)[:300], final={'balance_ok': None}, measure=None, success=None, best_during=None, steps=None)
with ThreadPoolExecutor(n) as ex: F = list(ex.map(fin, range(n)))
info = []
for k, jid in enumerate(ids):
    _, label, task = jid.split('|'); h = out[jid] or {}; f = F[k]
    info.append(dict(id=jid, slot=k, label=label, task=task, success=f['success'], measure=f['measure'], best_during=f['best_during'], steps=f['steps'],
                     balance_ok=f['final']['balance_ok'], lost=f.get('lost', False), summary=h.get('summary', ''), lessons=h.get('lessons', ''), claimed=h.get('best_throughput')))
os.makedirs('../rounds', exist_ok=True); json.dump(dict(name=name, run_id=run_id, episodes=info, finals=F), open(f'../rounds/{name}.json', 'w'), ensure_ascii=False, indent=1)
for e in info: print(e['id'], 'ПОТЕРЯН (DEVIATIONS 6)' if e['lost'] else '', 'мера', None if e['measure'] is None else round(e['measure'], 1), 'успех', e['success'], 'баланс', e['balance_ok'], 'шагов', e['steps'], 'заявлено', e['claimed'])
