#!/bin/bash
# ждёт окончания EVO-04
cd "$(dirname "$0")"; mkdir -p runs
while pgrep -f run_evo03.sh > /dev/null || pgrep -f run_evo04.sh > /dev/null; do sleep 60; done
xargs -P 2 -L 1 nice -n 5 python3 evo05.py < jobs.txt
