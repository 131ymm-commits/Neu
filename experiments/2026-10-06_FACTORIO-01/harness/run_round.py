# Раунд эпизодов: запустить демоны на слотах и собрать workflow. python3 run_round.py <имя> <задача:метка:правила_файл|-> ...  (до 6)
import json, subprocess, sys, time, os
from episode_prompt import prompt, SCHEMA
V = '/tmp/claude-0/flevenv/bin/python'; name = sys.argv[1]; specs = sys.argv[2:]; MAX = int(os.environ.get('MAX_STEPS', 20))
for k, s in enumerate(specs):
    task, label, rules = s.split(':')
    subprocess.Popen(f'{V} daemon.py {k} {name}_{label}_{task} {task} {MAX} /tmp/claude-0/fact/logs > /tmp/claude-0/fact/d{k}.log 2>&1', shell=True)
for k in range(len(specs)):
    for _ in range(100):
        if 'READY' in open(f'/tmp/claude-0/fact/d{k}.log').read(): break
        time.sleep(2)
jobs = []
for k, s in enumerate(specs):
    task, label, rules = s.split(':'); info = json.loads(subprocess.run(['python3', 'fle_step.py', str(k), 'info'], capture_output=True, text=True).stdout)
    jobs.append(dict(id=f'{name}|{label}|{task}', prompt=prompt(k, info['goal'], info['max_steps'], open(rules).read() if rules != '-' else None)))
src = (f"export const meta = {{ name: 'factorio-{name}', description: 'FACTORIO-01 {name}: {len(jobs)} эпизодов', phases: [{{ title: 'Эпизоды' }}] }}\n"
       f"const JOBS = {json.dumps(jobs, ensure_ascii=False)}\nconst S = {json.dumps(SCHEMA)}\nphase('Эпизоды')\n"
       "const res = await parallel(JOBS.map(j => () => agent(j.prompt, {label: j.id, phase: 'Эпизоды', schema: S})))\nconst out = {}\nJOBS.forEach((j, i) => { out[j.id] = res[i] })\nreturn {out}\n")
open(f'{name}.js', 'w').write(src); print(name, [j['id'] for j in jobs])
