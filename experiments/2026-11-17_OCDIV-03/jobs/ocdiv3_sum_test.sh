#!/bin/bash
# OCDIV-03 «тысячи»: анализ теста — после вывода всех 35 заданий теста и 3 повторов; сверка хешей регистрации и копий заданий, тесты кода и замка № 180, сборка, П1–П3 и описательное (B = 10 000, описательные нули — 2000, 4 процесса), прибор. Файл создан make_jobs3.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E2=experiments/2026-11-17_OCDIV-02
E=experiments/2026-11-17_OCDIV-03
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 $E/prereg_hashes3.py --verify --jobs
python3 tools/test_raw_status.py | tee "$OUT/raw_status_test.log" | tail -1
python3 $E/test_ocdiv3.py > "$OUT/tests_full.log" 2>&1 || true
grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
grep -q "провалов: 0" "$OUT/tests.log"
echo "== сборка"; python3 $E2/ocdiv2.py merge "$OUT/merged" test2 thousands gha_out/ocdiv3_test_*
python3 $E2/ocdiv2.py merge "$OUT/m_pilot2" pilot2 thousands gha_out/ocdiv2_pilot2_*
echo "== тест"; python3 $E/ocdiv3.py test "$OUT/analysis.json" "$OUT/merged" "$OUT/m_pilot2" gha_out/ocdiv3_pilot/pilot.json --boot 10000 --boot-descr 2000 --workers 4
echo "== прибор"; python3 $E2/trunc_check.py "$OUT/trunc.json" "gha_out/ocdiv3_test_*/answers_*.json" | tail -3
rm -rf "$OUT/merged" "$OUT/m_pilot2"          # сборки восстанавливаются из gha_out/ той же командой
