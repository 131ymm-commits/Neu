#!/bin/bash
# LENSES-2: прогон нуля X1oc в две очереди (2 ядра)
S=/tmp/claude-0/-home-claude/8c9bf095-e181-55d3-b75e-353e8e0f2d42/scratchpad/lenses2_score02
cd $S
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 SCORE02_COPY=$S/copy/experiments/2026-10-29_SCORE-02
lane1 () {
  python3 sim_null.py opus 0.037 100 2000 101 null/opus_s037_n100.jsonl --refit 400 2000 pi=0.42
  python3 sim_null.py opus 0.020 100 2000 102 null/opus_s020_n100.jsonl pi=0.42
  python3 sim_null.py opus 0.055 100 2000 103 null/opus_s055_n100.jsonl pi=0.42
  python3 sim_null.py opus 0.300 100 1000 104 null/opus_s300_n100.jsonl pi=0.42
}
lane2 () {
  python3 sim_null.py opus 0.037 59 2000 201 null/opus_s037_n59.jsonl --refit 400 2000 pi=0.42
  python3 sim_null.py opus 0.020 59 2000 202 null/opus_s020_n59.jsonl pi=0.42
  python3 sim_null.py opus 0.055 59 2000 203 null/opus_s055_n59.jsonl pi=0.42
  python3 sim_null.py opus 0.300 59 1000 204 null/opus_s300_n59.jsonl pi=0.42
}
lane1 > null/lane1.log 2>&1 &
lane2 > null/lane2.log 2>&1 &
wait
echo готово
