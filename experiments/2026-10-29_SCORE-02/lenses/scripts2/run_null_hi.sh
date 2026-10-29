#!/bin/bash
# LENSES-2: нуль X1oc в режиме почти единогласных вызовов (pi 0,85, clo 0,85)
S=/tmp/claude-0/-home-claude/8c9bf095-e181-55d3-b75e-353e8e0f2d42/scratchpad/lenses2_score02
cd $S
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 SCORE02_COPY=$S/copy/experiments/2026-10-29_SCORE-02
python3 sim_null.py opus 0.06 100 1500 301 null/hi_s060_n100.jsonl pi=0.85 clo=0.85
python3 sim_null.py opus 0.06 59 1500 302 null/hi_s060_n59.jsonl pi=0.85 clo=0.85
python3 sim_null.py opus 0.20 100 1000 303 null/hi_s200_n100.jsonl pi=0.85 clo=0.85
python3 sim_null.py opus 0.20 59 1000 304 null/hi_s200_n59.jsonl pi=0.85 clo=0.85
echo готово
