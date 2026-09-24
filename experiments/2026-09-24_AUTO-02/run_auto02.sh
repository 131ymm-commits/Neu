#!/bin/bash
# 10 сидов × 2 ветви, по 2 прогона параллельно
cd "$(dirname "$0")"; mkdir -p auto
for s in 20 21 22 23 24 25 26 27 28 29; do
  python3 auto_train.py A0 $s > auto/A0_s$s.log 2>&1 &
  python3 auto_train.py AW $s > auto/AW_s$s.log 2>&1
  wait
  echo "seed $s done $(date +%T)"
done
