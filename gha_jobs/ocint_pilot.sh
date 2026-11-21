#!/bin/bash
# OCINT-01: до регистрации — тесты кода, пилот на мирах с зерном пилота (в тест не входят) и на частях pilot трёх готовых
# сдвигов (в тест входят их части test). Всё — на GitHub Actions (слово автора 15.11.2026: все прогоны на сторонних площадках).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-15_OCINT-01
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 -c "import numpy, scipy, sklearn, sys, os; print('версии:', sys.version.split()[0], numpy.__version__, scipy.__version__, sklearn.__version__, '| ядер', os.cpu_count())"
echo "== тесты"; python3 $E/test_ocint.py > "$OUT/tests_full.log"; grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
echo "== пилот: миры (зерно пилота)"; python3 $E/ocint.py worlds "$OUT/pilot_worlds.json" --meta 7790000 --worlds 10 --exp 10 --truth 200 --boot 100 --workers 4
echo "== пилот: настоящие среды (части pilot трёх готовых сдвигов)"; python3 $E/ocint.py real "$OUT/pilot_real.json" --boot 400 --half 800 --curve 80 --quarter 50 --workers 4 \
  old:OCCOR-01=experiments/2026-11-14_OCCOR-01/pilot/out old:OCMIX-01=experiments/2026-11-14_OCMIX-01/pilot/out old:OCREP-01=experiments/2026-11-15_OCREP-01/pilot/out
