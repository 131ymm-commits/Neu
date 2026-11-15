#!/bin/bash
# OCSHIFT-01: анализ теста по PREREG — зарегистрированный сценарий для GitHub Actions (входит в хеши регистрации).
# Запуск: gha_jobs/ocshift_test.sh — копия шаблона gha_job_ocshift_test.sh, которая кладётся одним коммитом с сырым выводом теста
# (run/out/); пуш этого коммита запускает анализ один раз. Число повторов (10000) и процессов (4) закреплены здесь.
set -euo pipefail
OUT="$1"
E=experiments/2026-11-15_OCSHIFT-01
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 -c "import numpy, scipy, sklearn, sys, os; print('версии:', sys.version.split()[0], numpy.__version__, scipy.__version__, sklearn.__version__, '| ядер', os.cpu_count())"
python3 $E/prereg_hashes.py --verify
python3 $E/analyze_ocshift_test.py "$OUT/analysis.json" --boot 10000 --workers 4 new:$E/run/out
