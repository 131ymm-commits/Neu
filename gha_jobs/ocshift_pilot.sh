#!/bin/bash
# OCSHIFT-01: разбор пилота (только проверка цепочки и прогноз проверки метода — HYPOTHESIS). GitHub Actions.
# Повтор 15.11.2026: прогноз проверки метода — только по ID.
set -euo pipefail
OUT="$1"
E=experiments/2026-11-15_OCSHIFT-01
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 $E/pilot_ocshift.py $E/pilot/out "$OUT"
