#!/bin/bash
# OCDIV-02, совет 68, п. 0: проверка прибора — обрыв на пределе генерации и служебные токены в разборе ответа. По выводу пилотов OCDIV-02
# (их правда уже разобрана) и теста OCDIV-01 (для сравнения). Точность не печатается. Развилка записана до запуска (DECISIONS 17.11.2026).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-17_OCDIV-02
python3 -m pip install -q numpy==2.5.3
sha256sum $E/trunc_check.py
python3 $E/trunc_check.py "$OUT/trunc.json" 'gha_out/ocdiv2_pilot2_*/answers_*.json' 'gha_out/ocdiv2_pilot_*/answers_*.json' 'gha_out/ocdiv_test_*/answers_*.json'
