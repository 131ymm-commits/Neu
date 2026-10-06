#!/bin/bash
# Проверка кусак и подготовка следующего раунда (когда сбор уже сделан): ./tail_round.sh <следующий>
cd "$(dirname "$0")"
for k in 0 1 2 3 4 5; do /tmp/claude-0/flevenv/bin/python -c "
import factorio_rcon; r=factorio_rcon.RCONClient('localhost',2710$k,'factorio')
print('слот $k, убито врагами:', r.send_command('/sc local n=0 for _,v in pairs(game.forces.enemy.get_kill_count_statistics(game.surfaces[1]).input_counts) do n=n+v end rcon.print(n)').strip())" 2>/dev/null || echo "слот $k: нет ответа"; done | tee -a ../rounds/biters_check.log
python3 start_round.py "$1"
echo ГОТОВО
