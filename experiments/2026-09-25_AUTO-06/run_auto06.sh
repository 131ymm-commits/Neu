#!/bin/bash
# 12 сидов × 6 ветвей, по 3 прогона параллельно
cd "$(dirname "$0")"; mkdir -p auto
for s in $(seq 110 121); do
  for group in "A0 N1 N1024" "N4096 F1024 F4096"; do
    for a in $group; do python3 auto06_train.py $a $s > auto/${a}_s$s.log 2>&1 & done
    wait
  done
  echo "seed $s done $(date +%T)"
done
