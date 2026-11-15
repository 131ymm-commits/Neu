#!/bin/bash
# OCPOST-01: анализ теста по PREREG — зарегистрированный сценарий GitHub Actions (входит в хеши регистрации). В день теста
# копируется без изменений в gha_jobs/ocpost_test.sh одним коммитом с сырым выводом Kaggle (run/out/); пуш запускает анализ
# один раз. Число повторов (10000) и процессов (4) закреплены здесь.
set -euo pipefail
OUT="$1"
E=experiments/2026-11-15_OCPOST-01
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 -c "import numpy, scipy, sklearn, sys, os; print('версии:', sys.version.split()[0], numpy.__version__, scipy.__version__, sklearn.__version__, '| ядер', os.cpu_count())"
python3 $E/prereg_hashes.py --verify --job ocpost_test
echo "== тесты"; python3 $E/test_ocpost.py --real > "$OUT/tests_full.log"; grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
echo "== тест"; python3 $E/ocpost.py test "$OUT/analysis.json" --boot 10000 --workers 4 new:$E/run/out
