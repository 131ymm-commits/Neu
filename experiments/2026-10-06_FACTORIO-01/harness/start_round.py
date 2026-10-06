# Запуск раунда сравнения из расписания: python3 start_round.py C01 → убить демоны прошлых раундов, поднять 6 новых, написать C01.js
import json, subprocess, sys
name = sys.argv[1]; S = json.load(open('../schedule.json')); R = next(r for r in S['rounds'] if r['name'] == name)
# демоны прошлых раундов (не кампании ROCKET): по PID из ps, без pkill -f (ERRORS № 62)
ps = subprocess.run(['ps', '-eo', 'pid,args'], capture_output=True, text=True).stdout.splitlines()
pids = [l.split()[0] for l in ps if ' daemon.py ' in l and 'campaign_daemon' not in l]
if pids: subprocess.run(['kill', *pids]); print('убиты старые демоны:', len(pids))
specs = [f"{e['task']}:{name}-{e['arm']}-r{e['rep']}:{S['arms'][e['arm']]}" for e in R['episodes']]
subprocess.run(['python3', 'run_round.py', name, *specs], check=True)
