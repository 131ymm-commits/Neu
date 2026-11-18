#!/bin/bash
# OCDIV-04, шаг 3: пост-хок разбор совпадающих смещений на готовых ответах теста OCDIV-03 «тысяч» (совет 71, РАЗБОР-СМЕЩЕНИЙ;
# описательно, вес 0; мера закреплена до разбора — HYPOTHESIS 7aed3606). Тесты кода на заглушках, сборка test2, разбор (B = 2000,
# 4 процесса). Процессор раннера, без ключей.
set -euo pipefail
OUT="$1"
E2=experiments/2026-11-17_OCDIV-02
E=experiments/2026-11-18_OCDIV-04
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 $E/test_ocdiv4.py > "$OUT/tests_full.log" 2>&1 || true
grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
grep -q "провалов: 0" "$OUT/tests.log"
echo "== сборка"; python3 $E2/ocdiv2.py merge "$OUT/merged" test2 thousands gha_out/ocdiv3_test_*
echo "== разбор"; python3 $E/posthoc_offsets3.py "$OUT/merged" "$OUT/posthoc.json" --boot 2000 --workers 4
rm -rf "$OUT/merged"          # сборка восстанавливается из gha_out/ той же командой
