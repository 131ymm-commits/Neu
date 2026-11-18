#!/bin/bash
# OCDIV-04 «СОВПАДЕНИЕ-СМЕЩЕНИЙ»: анализ теста — после вывода всех 77 заданий и 3 повторов; сверка хешей регистрации, тесты кода и замка № 180, сборка, Р1-Т, Р1-Л, Р2-Т и описательное (B = 10 000, 4 процесса). Файл создан make_jobs4.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-18_OCDIV-04
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 $E/prereg_hashes4.py --verify --jobs
python3 tools/test_raw_status.py | tee "$OUT/raw_status_test.log" | tail -1
python3 $E/test_ocdiv4.py > "$OUT/tests_full.log" 2>&1 || true
grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
grep -q "провалов: 0" "$OUT/tests.log"
python3 $E/ocdiv4.py merge "$OUT/m_T" test3 thousands gha_out/ocdiv4_test_*
python3 $E/ocdiv4.py merge "$OUT/m_L" test3 length gha_out/ocdiv4_test_*
python3 $E/ocdiv4.py test "$OUT/analysis.json" "$OUT/m_T" "$OUT/m_L" gha_out/ocdiv4_sum_pilot3/pilot.json --boot 10000 --workers 4
echo "== прибор"; python3 experiments/2026-11-17_OCDIV-02/trunc_check.py "$OUT/trunc.json" "gha_out/ocdiv4_test_*/answers_*.json" | tail -3
rm -rf "$OUT/m_T" "$OUT/m_L"
