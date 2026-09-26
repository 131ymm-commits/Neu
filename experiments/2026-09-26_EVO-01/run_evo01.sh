#!/bin/bash
cd "$(dirname "$0")"; mkdir -p runs
for s in $(seq 0 19); do for t in T1 T2 T3; do for a in FIXED16 RANDOM16 RANDOM64 COEVO16 MIRROR16 ORACLE; do echo "$t $a $s"; done; done; done | xargs -P 2 -L 1 nice -n 5 python3 evo01.py
