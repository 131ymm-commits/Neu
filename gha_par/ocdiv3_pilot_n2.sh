#!/bin/bash
# OCDIV-03 «тысячи»: совет 70, Н2 — разбор пилота 2 «тысяч» кодом после правок совета: правило чтения П2 (Н1) по пяти средам с кросс-подгонкой d̂, различение страт, мощность и при τ из верхней границы; тесты кода с замками Н6. Файл создан make_jobs3.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E2=experiments/2026-11-17_OCDIV-02
E=experiments/2026-11-17_OCDIV-03
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 tools/test_raw_status.py | tee "$OUT/raw_status_test.log" | tail -1
python3 $E/test_ocdiv3.py > "$OUT/tests_full.log" 2>&1 || true
grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
grep -q "провалов: 0" "$OUT/tests.log"
python3 $E2/ocdiv2.py merge "$OUT/m_pilot2" pilot2 thousands gha_out/ocdiv2_pilot2_*
python3 $E/ocdiv3.py pilot "$OUT/pilot.json" "$OUT/m_pilot2" --boot 1000 --workers 4
rm -rf "$OUT/m_pilot2"          # сборка восстанавливается из gha_out/ocdiv2_pilot2_*/ той же командой
