#!/bin/bash
# ждёт окончания EVO-03
cd "$(dirname "$0")"; mkdir -p runs
while pgrep -f run_evo03.sh > /dev/null; do sleep 60; done
xargs -P 2 -L 1 nice -n 5 python3 evo04.py < jobs.txt
