#!/bin/bash
# OCPOST-01: до регистрации — тесты кода (с --real: сверка с зарегистрированным анализом OCSHIFT-01), сухой прогон на заглушках,
# пилот на десяти средах теста OCSHIFT-01 (мощность; в тест OCPOST-01 они не входят) и пилотные миры (зерно 7 890 000:
# время повтора, правда wc POST и wc FIXED, разброс и хвосты M4). Всё — на GitHub Actions (слово автора 15.11.2026).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-15_OCPOST-01
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 -c "import numpy, scipy, sklearn, sys, os; print('версии:', sys.version.split()[0], numpy.__version__, scipy.__version__, sklearn.__version__, '| ядер', os.cpu_count())"
echo "== тесты"; python3 $E/test_ocpost.py --real > "$OUT/tests_full.log"; grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
echo "== сухой прогон"; python3 $E/dry_ocpost.py "$OUT/dry" --boot 200 > "$OUT/dry_full.log"; grep -E "как ожидалось|НЕ КАК|сухой прогон" "$OUT/dry_full.log" | tee "$OUT/dry.log"
echo "== пилот: среды теста OCSHIFT-01"; python3 $E/ocpost.py pilot "$OUT/pilot_envs.json" --boot 2000 --workers 4 --ref gha_out/ocshift_test/analysis.json \
  new:experiments/2026-11-15_OCSHIFT-01/run/out
echo "== пилот: миры (зерно пилота)"; python3 $E/ocpost.py worlds "$OUT/pilot_worlds.json" --meta 7890000 --first 0 --worlds 10 --exp 40 --truth 1000 --boot 200 --workers 4
python3 $E/ocpost.py tail "$OUT/pilot_tail.json" "$OUT/pilot_worlds.json"
