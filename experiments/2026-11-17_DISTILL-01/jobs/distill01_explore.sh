#!/bin/bash
# DISTILL-01 «ДИСТИЛЛЯЦИЯ-ГОЛОВ»: разведка — формулы ошибок семи голов от признаков входа (PLAN.md 1d1fcc62).
# Построение — пилот 2 OCDIV-02; отложенные — тесты OCDIV-02 и OCDIV-01 (пост-хок, описательно). Процессор раннера, без ключей.
set -euo pipefail
OUT="$1"
E=experiments/2026-11-17_DISTILL-01
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 $E/test_distill.py | tee "$OUT/tests.log"
python3 $E/distill.py "$OUT/distill.json" --fit 'gha_out/ocdiv2_pilot2_*/answers_*.json' \
  --hold 'test_ocdiv2=gha_out/ocdiv2_test_*/answers_*.json' 'test_ocdiv1=gha_out/ocdiv_test_*/answers_*.json' \
  --t4 'test_ocdiv2=gha_out/ocdiv2_sum_test/analysis.json' | tee "$OUT/log_distill.txt"
