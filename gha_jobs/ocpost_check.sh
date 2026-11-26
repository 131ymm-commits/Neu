#!/bin/bash
# OCPOST-01: проверка кода после правок совета 64 (правило NaN в Т, база SHIFT, правила чтения) — до регистрации:
# тесты с --real (сверка с зарегистрированным анализом OCSHIFT-01) и сухой прогон на заглушках. Всё — на GitHub Actions.
set -euo pipefail
OUT="$1"
E=experiments/2026-11-15_OCPOST-01
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 -c "import numpy, scipy, sklearn, sys, os; print('версии:', sys.version.split()[0], numpy.__version__, scipy.__version__, sklearn.__version__, '| ядер', os.cpu_count())"
echo "== тесты"; python3 $E/test_ocpost.py --real > "$OUT/tests_full.log"; grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
echo "== сухой прогон"; python3 $E/dry_ocpost.py "$OUT/dry" --boot 200 > "$OUT/dry_full.log"; grep -E "как ожидалось|НЕ КАК|сухой прогон" "$OUT/dry_full.log" | tee "$OUT/dry.log"
