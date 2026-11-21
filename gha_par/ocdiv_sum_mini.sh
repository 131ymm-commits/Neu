#!/bin/bash
# OCDIV-01: разбор мини-пилота формата (совет 66, п. 1; порог записан в DECISIONS до запуска), хронометраж бутстрепа на среде
# пилота 2 («можно», инженер) и пересчёт мощности и ожиданий с E8 (совет 66, п. 4). Запуск — после всех 7 заданий мини-пилота.
set -euo pipefail
OUT="$1"
E=experiments/2026-11-16_OCDIV-01
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 -c "import numpy, scipy, sklearn, sys, os; print('версии:', sys.version.split()[0], numpy.__version__, scipy.__version__, sklearn.__version__, '| ядер', os.cpu_count())"
echo "== мини-пилот формата (X = 3, p = 2)"
python3 $E/ocdiv.py merge "$OUT/merged_mini" mini 600 random gha_out/ocdiv_mini_*
python3 $E/ocdiv.py mini "$OUT/mini.json" "$OUT/merged_mini"
echo "== хронометраж бутстрепа (среда пилота 2)"
python3 $E/ocdiv.py merge "$OUT/merged_p2" pilot 600 random gha_out/ocdiv_pilot2_*
python3 $E/ocdiv.py timing "$OUT/timing.json" "$OUT/merged_p2" --boot 200 --workers 4
echo "== мощность и ожидания"
python3 $E/power_ocdiv.py gha_out/ocdiv_sum_pilot2/pilot2.json "$OUT/expect_ocdiv.json"
rm -rf "$OUT/merged_mini" "$OUT/merged_p2"          # сборки восстанавливаются той же командой
