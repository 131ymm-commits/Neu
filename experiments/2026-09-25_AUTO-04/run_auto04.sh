#!/bin/bash
# 20 сидов × 3 ветви (A0, AW, AR), по 3 прогона параллельно
cd "$(dirname "$0")"; mkdir -p auto
for s in $(seq 50 69); do
  python3 auto04_train.py A0 $s > auto/A0_s$s.log 2>&1 &
  python3 auto04_train.py AW $s > auto/AW_s$s.log 2>&1 &
  python3 auto04_train.py AR $s > auto/AR_s$s.log 2>&1
  wait
  echo "seed $s done $(date +%T)"
done
