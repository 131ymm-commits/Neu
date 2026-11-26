#!/bin/bash
# DISTILL-05 «ТОКЕН-ОПЕРАТОРЫ»: проверка кода разведки на раннере (тесты на заглушках; данных голов не читает). Процессор, без ключей.
set -euo pipefail
OUT="$1"
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 -c "import numpy, scipy, platform; print('версии: python', platform.python_version(), 'numpy', numpy.__version__, 'scipy', scipy.__version__)" | tee "$OUT/versions.txt"
python3 experiments/2026-11-25_DISTILL-05/test_explore_d5.py > "$OUT/tests.log" 2>&1 || true
grep -E "^✗|провалов" "$OUT/tests.log"
grep -q "провалов: 0" "$OUT/tests.log"
