#!/bin/bash
# OCDIV-01: анализ теста — после всех 35 заданий извлечения (7 голов × 5 сред OCPOST-01). Сверка хешей регистрации и копий заданий,
# тесты кода, сборка ответов новых голов, D1–D5 и N (ocdiv.py test, B = 10 000, 4 процесса). Шаблон — jobs/ocdiv_sum_test.sh (PREREG §11).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-16_OCDIV-01
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 -c "import numpy, scipy, sklearn, sys, os; print('версии:', sys.version.split()[0], numpy.__version__, scipy.__version__, sklearn.__version__, '| ядер', os.cpu_count())"
python3 $E/prereg_hashes.py --verify --jobs
echo "== тесты"; python3 $E/test_ocdiv.py > "$OUT/tests_full.log" 2>&1; grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
echo "== сборка"; python3 $E/ocdiv.py merge "$OUT/merged" test 0 first gha_out/ocdiv_test_*
echo "== тест"; python3 $E/ocdiv.py test "$OUT/analysis.json" "$OUT/merged" --boot 10000 --workers 4
rm -rf "$OUT/merged"          # сборка восстанавливается из gha_out/ocdiv_test_*/ той же командой
