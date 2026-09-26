#!/bin/bash
# Общая очередь после перезапуска контейнера 26.09: пропускает уже сделанные прогоны.
set -u
cd "$(dirname "$0")"
resume () {   # $1 — каталог, $2 — скрипт; строки jobs.txt: "задача ветвь сид"
  ( cd "$1"; mkdir -p runs
    while read t a s; do [ -f "runs/${t}_${a}_s${s}.json" ] || echo "$t $a $s"; done < jobs.txt | xargs -r -P 2 -L 1 nice -n 5 python3 "$2" )
}
resume 2026-09-26_EVO-03 evo03.py; echo "EVO-03 готово $(date +%T)"
( cd 2026-09-26_AUTO-08; for s in 150 151; do [ -f diag_preLN/F1024_s$s.json ] || nice -n 5 python3 auto08_diag_preLN.py F1024 $s > diag_F1024_s$s.log 2>&1 & done; wait ); echo "AUTO-08 диагностика готово $(date +%T)"
resume 2026-09-26_EVO-04 evo04.py; echo "EVO-04 готово $(date +%T)"
resume 2026-09-26_EVO-05 evo05.py; echo "EVO-05 готово $(date +%T)"
