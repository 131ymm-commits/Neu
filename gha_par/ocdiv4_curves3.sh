#!/bin/bash
# OCDIV-04 «СОВПАДЕНИЕ-СМЕЩЕНИЙ»: третий контроль N3c, задание 1 (HYPOTHESIS-ADDENDUM-2, совет 72): кривые «доза–прирост» по средам «тысяч» на первой половине задач пилота, цели, δ_e (R = 20, 4 процесса). Файл создан make_jobs4.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-18_OCDIV-04
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 tools/test_raw_status.py | tee "$OUT/raw_status_test.log" | tail -1
python3 $E/test_ocdiv4.py > "$OUT/tests_full.log" 2>&1 || true
grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
grep -q "провалов: 0" "$OUT/tests.log"
python3 $E/ocdiv4.py merge "$OUT/m_T" pilot3 thousands gha_out/ocdiv4_pilot_*
python3 $E/ocdiv4.py curves3 "$OUT/curves3.json" "$OUT/m_T" gha_out/ocdiv4_sum_pilot3/pilot.json --R 20 --workers 4
rm -rf "$OUT/m_T"
