#!/bin/bash
# OCDIV-01: разбор пилотов. Пилот 1 (первые 300 задач — выборка смещена, ERRORS № 175) — описательно, без мощности.
# Пилот 2 (600 случайных задач каждой из десяти сред OCSHIFT-01) — годность, толпа, FIXED-нов, совпадение ошибок (D1 сырая и
# с поправкой на точность), мощность D1–D5 и N на тесте, вероятность, что опыт определён (ocdiv.py pilot). Запуск — после всех 20 заданий пилота 2.
set -euo pipefail
OUT="$1"
E=experiments/2026-11-16_OCDIV-01
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 -c "import numpy, scipy, sklearn, sys, os; print('версии:', sys.version.split()[0], numpy.__version__, scipy.__version__, sklearn.__version__, '| ядер', os.cpu_count())"
echo "== пилот 1 (описательно)"
python3 $E/ocdiv.py merge "$OUT/merged1" pilot 300 first gha_out/ocdiv_pilot_*
python3 $E/ocdiv.py pilot "$OUT/pilot1.json" "$OUT/merged1" --boot 200 --no-power
echo "== пилот 2"
python3 $E/ocdiv.py merge "$OUT/merged2" pilot 600 random gha_out/ocdiv_pilot2_*
python3 $E/ocdiv.py pilot "$OUT/pilot2.json" "$OUT/merged2" --boot 200
rm -rf "$OUT/merged1" "$OUT/merged2"          # сборки восстанавливаются из gha_out/ocdiv_pilot*_*/ той же командой
