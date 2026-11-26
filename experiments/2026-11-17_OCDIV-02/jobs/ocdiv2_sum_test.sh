#!/bin/bash
# OCDIV-02 «ОЦЕНЩИК-ТРУДНЫЙ-СДВИГ»: анализ теста — после всех 35 заданий теста и повтора; сверка хешей регистрации и копий заданий, тесты кода, тест замка № 180, сборка, Т1–Т4 (B = 10 000, 4 процесса). Файл создан make_jobs2.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-17_OCDIV-02
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 $E/prereg_hashes2.py --verify --jobs
python3 tools/test_raw_status.py | tee "$OUT/raw_status_test.log" | tail -1
echo "== тесты"; python3 $E/test_ocdiv2.py > "$OUT/tests_full.log" 2>&1; grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
echo "== сборка"; python3 $E/ocdiv2.py merge "$OUT/merged" test2 length gha_out/ocdiv2_test_*
echo "== тест"; python3 $E/ocdiv2.py test "$OUT/analysis.json" "$OUT/merged" --boot 10000 --workers 4
rm -rf "$OUT/merged"          # сборка восстанавливается из gha_out/ocdiv2_test_*/ той же командой
