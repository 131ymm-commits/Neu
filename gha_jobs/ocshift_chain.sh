#!/bin/bash
# OCSHIFT-01: до регистрации — тесты, сухой прогон на заглушках, прогон правил на трёх готовых сдвигах как на средах
# (пост-хок; опорой не считается) и мощность. Всё — на GitHub Actions (слово автора 15.11.2026).
# Повтор 15.11.2026: после правок до регистрации (max-T для R1, проверка метода только по ID, wc ONE-BEST).
# Повтор 2, 15.11.2026: результаты первого повтора не закоммитились (два прогона писали в одну папку); код — с R2 вторым способом.
set -euo pipefail
OUT="$1"
E=experiments/2026-11-15_OCSHIFT-01
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 -c "import numpy, scipy, sklearn, sys, os; print('версии:', sys.version.split()[0], numpy.__version__, scipy.__version__, sklearn.__version__, '| ядер', os.cpu_count())"
echo "== тесты"; python3 $E/test_ocshift.py | tee "$OUT/tests.log"
echo "== сухой прогон"; python3 $E/dry_ocshift.py "$OUT/dry" --boot 60
echo "== цепочка: части pilot трёх готовых сдвигов"; python3 $E/analyze_ocshift_test.py "$OUT/chain_old_pilot.json" --boot 2000 \
  old:OCCOR-01=experiments/2026-11-14_OCCOR-01/pilot/out old:OCMIX-01=experiments/2026-11-14_OCMIX-01/pilot/out old:OCREP-01=experiments/2026-11-15_OCREP-01/pilot/out
echo "== цепочка: части test трёх готовых сдвигов"; python3 $E/analyze_ocshift_test.py "$OUT/chain_old_test.json" --boot 1000 \
  old:OCCOR-01=experiments/2026-11-14_OCCOR-01/run/out old:OCMIX-01=experiments/2026-11-14_OCMIX-01/run/out old:OCREP-01=experiments/2026-11-15_OCREP-01/run/out
echo "== мощность"; python3 $E/power_ocshift.py "$OUT"
