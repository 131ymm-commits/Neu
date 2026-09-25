#!/bin/bash
# ждёт окончания AUTO-06, затем 12 сидов × 8 ветвей, по 3 прогона параллельно (ветвь Z исключена, см. PREREG)
cd "$(dirname "$0")"; mkdir -p auto
while pgrep -f run_auto06.sh > /dev/null; do sleep 60; done
for s in $(seq 130 141); do
  for group in "A0 N S" "P C F" "B M"; do
    for a in $group; do python3 auto07_train.py $a $s > auto/${a}_s$s.log 2>&1 & done
    wait
  done
  echo "seed $s done $(date +%T)"
done
