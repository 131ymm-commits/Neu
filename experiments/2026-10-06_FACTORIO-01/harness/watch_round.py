# Наблюдатель раунда: финальная мера каждого слота сразу, как только его голова закончила (ERRORS № 69 — раунд C05 потерян,
# потому что контейнер перезапустился между концом голов и сбором). Итог демон пишет в свой лог; collect_round.py берёт его оттуда.
#   nohup python3 watch_round.py <C0X> <run_id> &
import json, os, subprocess, sys, time
name, run_id = sys.argv[1], sys.argv[2]
J = f'/root/.claude/projects/-home-user/368a3030-ed6f-5d75-8ccd-d3417f8f1866/subagents/workflows/{run_id}/journal.jsonl'
jobs = json.loads(open(f'{name}.js').read().split('const JOBS = ')[1].split('\nconst S')[0])
slot_of = {j['id']: k for k, j in enumerate(jobs)}
label_of, done = {}, set()
procs = []
while len(done) < len(jobs):
    if os.path.exists(J):
        for line in open(J):
            d = json.loads(line)
            if d.get('type') == 'started': label_of[d['key']] = d['label']
            elif d.get('key') in label_of and d.get('type') not in ('started', 'launched'):
                lab = label_of[d['key']]
                if lab not in done:
                    done.add(lab); k = slot_of[lab]
                    print(time.strftime('%H:%M:%S'), 'голова закончила:', lab, d.get('type'), '→ мера слота', k, flush=True)
                    procs.append(subprocess.Popen(['python3', 'fle_step.py', str(k), 'final'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    time.sleep(10)
for p in procs: p.wait()
print('ВСЕ ЗАМЕРЫ СДЕЛАНЫ', flush=True)
