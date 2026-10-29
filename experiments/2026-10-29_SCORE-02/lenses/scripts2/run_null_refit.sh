#!/bin/bash
# LENSES-2: фиксированная карта против пересчитываемой в режиме почти единогласных вызовов
S=/tmp/claude-0/-home-claude/8c9bf095-e181-55d3-b75e-353e8e0f2d42/scratchpad/lenses2_score02
cd $S
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 SCORE02_COPY=$S/copy/experiments/2026-10-29_SCORE-02
( python3 sim_null.py opus 0.20 100 400 401 null/hiR_s200_n100.jsonl --refit 400 2000 pi=0.85 clo=0.85
  python3 sim_null.py opus 0.06 100 400 403 null/hiR_s060_n100.jsonl --refit 400 2000 pi=0.85 clo=0.85 ) > null/refit1.log 2>&1 &
( python3 sim_null.py opus 0.20 59 400 402 null/hiR_s200_n59.jsonl --refit 400 2000 pi=0.85 clo=0.85
  python3 sim_null.py opus 0.06 59 400 404 null/hiR_s060_n59.jsonl --refit 400 2000 pi=0.85 clo=0.85 ) > null/refit2.log 2>&1 &
wait
echo готово
