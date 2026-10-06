# Расписание этапа 2 (сравнение на Q): руки × задачи × 3 повтора, перемешано (seed 20261006, PREREG), раунды по 6 эпизодов (слоты 0–5).
# Руки PREREG: 0, S1, S2, S3, Z; ветвь U и контроль Z_U — DEVIATIONS п. 4. python3 make_schedule.py → ../schedule.json
import json, random
ARMS = {'A0': '-', 'S1': '../rules/S1_final.md', 'S2': '../rules/S2_final.md', 'S3': '../rules/S3_final.md', 'Z': '../rules/Z.md', 'U': '../rules/U.md', 'ZU': '../rules/Z_U.md'}
Q = ['plastic_bar_throughput', 'sulfur_throughput', 'battery_throughput', 'steel_plate_throughput', 'engine_unit_throughput', 'military_science_pack_throughput']
items = [dict(arm=a, task=t, rep=r) for a in ARMS for t in Q for r in (1, 2, 3)]
random.Random(20261006).shuffle(items)
rounds = [dict(name=f'C{k // 6 + 1:02d}', episodes=items[k:k + 6]) for k in range(0, len(items), 6)]
json.dump(dict(seed=20261006, arms=ARMS, tasks=Q, n=len(items), rounds=rounds), open('../schedule.json', 'w'), ensure_ascii=False, indent=1)
print(len(items), 'эпизодов,', len(rounds), 'раундов; C01:', [(e['arm'], e['task'][:8]) for e in rounds[0]['episodes']])
