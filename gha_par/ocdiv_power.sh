#!/bin/bash
# OCDIV-01: мощность правил на тесте по пилоту 2 и ожидания для калибровки (power_ocdiv.py → expect_ocdiv.json):
# τ̂ и τ = s, знаковые — с предохранителем «без одного диапазона» (Монте-Карло, зерно 7 990 000).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-16_OCDIV-01
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 $E/power_ocdiv.py gha_out/ocdiv_sum_pilot2/pilot2.json "$OUT/expect_ocdiv.json"
