#!/bin/bash
# OCDIV-01: производные числа отчёта — незнание и самообман разнородной толпы (точки тем же кодом, что анализ, со сверкой с точками правил),
# средние по средам и вес опоры по PREREG §10. Сборка чисел; вердиктов не меняет. Запуск — копией в gha_par/ после того, как в ветке лежит
# gha_out/ocdiv_sum_test/analysis.json. facts_ocdiv.py не входит в хеши регистрации (написан после прихода сырого вывода теста и до вывода
# анализа — DEVIATIONS, п. 2); его sha256 — в логе.
set -euo pipefail
OUT="$1"
E=experiments/2026-11-16_OCDIV-01
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
test -s gha_out/ocdiv_sum_test/analysis.json
python3 $E/prereg_hashes.py --verify --jobs
sha256sum $E/facts_ocdiv.py gha_out/ocdiv_sum_mini/expect_ocdiv.json gha_out/ocdiv_sum_test/analysis.json
python3 $E/ocdiv.py merge "$OUT/merged" test 0 first gha_out/ocdiv_test_*
python3 $E/facts_ocdiv.py gha_out/ocdiv_sum_test/analysis.json "$OUT/merged" gha_out/ocdiv_sum_mini/expect_ocdiv.json "$OUT/facts_ocdiv.json"
rm -rf "$OUT/merged"          # сборка восстанавливается из gha_out/ocdiv_test_*/ той же командой
