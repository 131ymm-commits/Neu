#!/bin/bash
# DISTILL-03 «A-НА-B»: мощность при k = 6 (совет 76, п. 3) — одна голова выпала, «да» только при ранге 1 из 720. Подматрицы 6 × 6
# пилота T_X19 (gha_out/distill03_power/pilot.json, 9f8af9aa) без каждой из 7 голов; шум — из их остатков; δ = D подматрицы;
# четыре модели шума, два семейства; в PREREG — наименьшая. Тесты кода — до счёта. Процессор, без ключей, без данных теста.
set -euo pipefail
OUT=$(realpath "$1")
E3=experiments/2026-11-19_DISTILL-03
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 -c "import numpy, platform; print('версии: python', platform.python_version(), 'numpy', numpy.__version__)" | tee "$OUT/versions.txt"
python3 $E3/test_ab.py > "$OUT/tests.log" 2>&1; grep -E "^✗|провалов" "$OUT/tests.log" | tail -3
grep -q "провалов: 0" "$OUT/tests.log"
T0=$(date +%s)
python3 $E3/power_ab.py gha_out/distill03_power/pilot.json "$OUT/power_k6.json" --k6 | tee "$OUT/power_k6.log"
echo "всего: $(( $(date +%s) - T0 )) с" | tee "$OUT/time.log"
