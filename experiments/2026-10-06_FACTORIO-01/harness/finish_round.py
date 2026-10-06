# Финальная мера всех слотов раунда (после ответа голов): python3 finish_round.py <n>
import json, subprocess, sys
for k in range(int(sys.argv[1])):
    r = subprocess.run(['python3', 'fle_step.py', str(k), 'final'], capture_output=True, text=True).stdout; d = json.loads(r)
    print(k, round(d['measure'], 1), d['success'], 'лучшее во время', d['best_during'], 'шагов', d['steps'], 'очищено', d['final']['cleared_items'])
