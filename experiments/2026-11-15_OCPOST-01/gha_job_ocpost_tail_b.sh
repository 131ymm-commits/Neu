#!/bin/bash
# OCPOST-01: проверка хвоста Т, часть B — миры 20–39 (зерно 7 840 000; модель OCINT-01) — зарегистрированный сценарий
# GitHub Actions (входит в хеши регистрации; копия кладётся в gha_jobs/ocpost_tail_b.sh в день запуска и сверяется с шаблоном).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-15_OCPOST-01
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 -c "import numpy, scipy, sklearn, sys, os; print('версии:', sys.version.split()[0], numpy.__version__, scipy.__version__, sklearn.__version__, '| ядер', os.cpu_count())"
python3 $E/prereg_hashes.py --verify --job ocpost_tail_b
python3 $E/ocpost.py worlds "$OUT/worlds_b.json" --meta 7840000 --first 20 --worlds 20 --exp 300 --truth 2000 --boot 100 --workers 4
