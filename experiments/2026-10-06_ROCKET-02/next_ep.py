# Переход между эпизодами ROCKET-02 (оркестратор): end → снимок → проверка мира по игре (health.py) → заметка в журнал → строка README → begin следующего.
#   python3 next_ep.py <закончен> "<итог эпизода одной строкой>" <следующий> <роль> [шагов]
import json, subprocess, sys
from orch import send
done, summary, nxt, role = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]; ms = sys.argv[5] if len(sys.argv) > 5 else '40'
e = send(6, dict(cmd='end', ep=done, max_steps=0))
# сохранение мира на диск (переживёт перезапуск контейнера) и переподключение демона без сброса
ck = send(6, dict(cmd='checkpoint', ep='rocket2_ckpt', max_steps=0)); print('сохранение:', ck.get('saved'), ck.get('size'))
subprocess.run(['./daemon_ctl.sh', 'attach'], check=True)
subprocess.run(f'cp campaign/NOTES.md snapshots/NOTES_after_{done}.md && cp campaign/campaign.jsonl snapshots/campaign_after_{done}.jsonl', shell=True, check=True)
H = subprocess.run(['/tmp/claude-0/flevenv/bin/python', 'health.py'], capture_output=True, text=True).stdout.splitlines()
d = json.loads(H[0]); itog = H[-1].replace('ИТОГ: ', '')
open('campaign/NOTES.md', 'a').write(f"\n\n## [оркестратор] Проверка мира по игре после {done}\n{itog}\nСтатусы машин: {json.dumps(d['statuses'], ensure_ascii=False)}\n"
                                      f"Выпуск за 10 мин: {json.dumps(d['made_10min'], ensure_ascii=False)}\nУничтожено врагами за всё время: {json.dumps(d['killed_by_enemy'], ensure_ascii=False)}\n")
s = open('README.md').read()
s = s.replace(f"| {done} |", f"| {done} |", 1)
lines = s.split('\n'); i = next(k for k, l in enumerate(lines) if l.startswith(f'| {done} |'))
role_name = lines[i].split('|')[2].strip()
lines[i] = f"| {done} | {role_name} | {e.get('steps')} | {summary} **Проверка по игре:** {itog} |"
ROLE = {'builder': 'строитель', 'defense': 'оборона и восстановление', 'logistics': 'логистика топлива', 'chief': 'главный инженер'}
lines.insert(i + 1, f"| {nxt} | {ROLE.get(role, role)} | — | идёт |")
open('README.md', 'w').write('\n'.join(lines))
print(itog); print(subprocess.run(['python3', 'run_ep.py', nxt, role, ms], capture_output=True, text=True).stdout)
