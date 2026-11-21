#!/bin/bash
# OCINT-01: 13 настоящих сред (десять сред теста OCSHIFT-01 и части test трёх готовых сдвигов) — зарегистрированный сценарий.
set -euo pipefail
OUT="$1"
E=experiments/2026-11-15_OCINT-01
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 $E/prereg_hashes.py --verify
python3 $E/ocint.py real "$OUT/real.json" --boot 1000 --half 2000 --curve 200 --quarter 100 --workers 4 \
  new:experiments/2026-11-15_OCSHIFT-01/run/out \
  old:OCCOR-01=experiments/2026-11-14_OCCOR-01/run/out old:OCMIX-01=experiments/2026-11-14_OCMIX-01/run/out old:OCREP-01=experiments/2026-11-15_OCREP-01/run/out
