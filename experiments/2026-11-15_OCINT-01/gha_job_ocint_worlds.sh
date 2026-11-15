#!/bin/bash
# OCINT-01: миры теста (зерно 7 700 000) — зарегистрированный сценарий GitHub Actions (входит в хеши регистрации).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-15_OCINT-01
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 -c "import numpy, scipy, sklearn, sys, os; print('версии:', sys.version.split()[0], numpy.__version__, scipy.__version__, sklearn.__version__, '| ядер', os.cpu_count())"
python3 $E/prereg_hashes.py --verify
echo "== тесты"; python3 $E/test_ocint.py > "$OUT/tests_full.log"; grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
echo "== миры теста"; python3 $E/ocint.py worlds "$OUT/worlds.json" --meta 7700000 --worlds 10 --exp 60 --truth 2000 --boot 200 --workers 4
