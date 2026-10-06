# Финальная мера ред. 2 на живом слоте через голый RCON (карта не сбрасывается): python3 measure_slot.py <slot> <предмет> <квота> <выход.json>
import json, sys
sys.path.insert(0, '/tmp/claude-0/fact'); from rcon import RCON
from measure import final_measure_cmd
slot, target, quota, outp = int(sys.argv[1]), sys.argv[2], int(sys.argv[3]), sys.argv[4]
r = RCON(port=27100 + slot, pw='factorio'); res = final_measure_cmd(r.cmd, target, quota)
json.dump(res, open(outp, 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: res[k] for k in ('cleared_items', 'measure', 'balance_ok', 'success')}, ensure_ascii=False), 'w1', round(res['w1']['norm'], 1), 'w2', round(res['w2']['norm'], 1))
for w in ('w1', 'w2'): print(w, {k: v for k, v in res[w]['balance'].items() if v['mined'] or v['used']})
