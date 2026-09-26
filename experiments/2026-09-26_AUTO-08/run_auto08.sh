#!/bin/bash
# 12 сидов × 4 ветви, по 4 прогона параллельно (по одному потоку torch на прогон)
cd "$(dirname "$0")"; mkdir -p auto
for s in $(seq 150 161); do
  for a in A0 F256 F1024 S1024; do python3 auto08_train.py $a $s > auto/${a}_s$s.log 2>&1 & done
  wait
  echo "seed $s done $(date +%T)"
done
