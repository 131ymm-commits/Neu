#!/bin/bash
# Сбор раунда сравнения и подготовка следующего: ./next_round.sh <собрать> <run_id> <следующий|->
set -e
cd "$(dirname "$0")"
python3 collect_round.py "$1" "$2" 6
# проверка кусак после раунда (DEVIATIONS п. 2): сколько своих построек убила сила enemy на слотах 0–5
for k in 0 1 2 3 4 5; do /tmp/claude-0/flevenv/bin/python -c "
import factorio_rcon; r=factorio_rcon.RCONClient('localhost',2710$k,'factorio')
print('слот $k, убито врагами:', r.send_command('/sc local n=0 for _,v in pairs(game.forces.enemy.get_kill_count_statistics(game.surfaces[1]).input_counts) do n=n+v end rcon.print(n)').strip())" 2>/dev/null || echo "слот $k: нет ответа"; done | tee -a ../rounds/biters_check.log
[ "$3" != "-" ] && python3 start_round.py "$3"
echo ГОТОВО
