#!/bin/bash
cd "$(dirname "$0")"; mkdir -p runs
xargs -P 2 -L 1 nice -n 5 python3 evo03.py < jobs.txt
