#!/bin/bash
# ждёт окончания EVO-01, затем 3 задачи × 5 ветвей × 20 сидов по 2 параллельно
cd "$(dirname "$0")"; mkdir -p runs
while pgrep -f run_evo01.sh > /dev/null; do sleep 60; done
for s in $(seq 0 19); do for t in T1 T2 T3; do for a in BASE HGT LIFE TWO SPLIT; do echo "$t $a $s"; done; done; done | xargs -P 2 -L 1 nice -n 5 python3 evo02.py
