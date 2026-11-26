#!/bin/bash
# OCPOST-01: правило Т по двум частям миров — зарегистрированный сценарий GitHub Actions (входит в хеши регистрации; копия
# кладётся в gha_jobs/ocpost_tail_sum.sh после того, как результаты обеих частей закоммичены в ветку).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-15_OCPOST-01
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 -c "import numpy, scipy, sklearn, sys, os; print('версии:', sys.version.split()[0], numpy.__version__, scipy.__version__, sklearn.__version__, '| ядер', os.cpu_count())"
python3 $E/prereg_hashes.py --verify --job ocpost_tail_sum
python3 $E/ocpost.py tail "$OUT/tail.json" gha_out/ocpost_tail_a/worlds_a.json gha_out/ocpost_tail_b/worlds_b.json
