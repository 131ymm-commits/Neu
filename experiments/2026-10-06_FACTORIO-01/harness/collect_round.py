# Сбор раунда: финальная мера всех слотов (демон, мера ред. 2) + ответы голов из workflow → rounds/<name>.json
#   python3 collect_round.py <name> <run_id> <n_slots>
import json, subprocess, sys, os
from concurrent.futures import ThreadPoolExecutor
name, run_id, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
W = f'/root/.claude/projects/-home-user/368a3030-ed6f-5d75-8ccd-d3417f8f1866/workflows/{run_id}.json'
res = json.load(open(W))['result']; res = json.loads(res) if isinstance(res, str) else res; out = res['out']
def fin(k): return json.loads(subprocess.run(['python3', 'fle_step.py', str(k), 'final'], capture_output=True, text=True, timeout=1800).stdout)
with ThreadPoolExecutor(n) as ex: F = list(ex.map(fin, range(n)))
info = []
ids = list(out.keys())
for k, jid in enumerate(ids):
    _, label, task = jid.split('|'); h = out[jid] or {}; f = F[k]
    info.append(dict(id=jid, slot=k, label=label, task=task, success=f['success'], measure=f['measure'], best_during=f['best_during'], steps=f['steps'],
                     balance_ok=f['final']['balance_ok'], summary=h.get('summary', ''), lessons=h.get('lessons', ''), claimed=h.get('best_throughput')))
os.makedirs('../rounds', exist_ok=True); json.dump(dict(name=name, run_id=run_id, episodes=info, finals=F), open(f'../rounds/{name}.json', 'w'), ensure_ascii=False, indent=1)
for e in info: print(e['id'], 'мера', round(e['measure'], 1), 'успех', e['success'], 'баланс', e['balance_ok'], 'шагов', e['steps'], 'заявлено', e['claimed'])
