#!/bin/bash
# OCDIV-02 «ОЦЕНЩИК-ТРУДНЫЙ-СДВИГ»: разбор пилота 2 (подсказка только из ID) — сборка двух семейств, правило выбора семейства, мощность Т1–Т4. Файл создан make_jobs2.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-17_OCDIV-02
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 tools/test_raw_status.py | tail -1
python3 $E/test_ocdiv2.py > "$OUT/tests_full.log" 2>&1; grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
python3 $E/ocdiv2.py merge "$OUT/m_thousands" pilot2 thousands gha_out/ocdiv2_pilot2_*
python3 $E/ocdiv2.py merge "$OUT/m_length" pilot2 length gha_out/ocdiv2_pilot2_*
python3 $E/ocdiv2.py pilot "$OUT/pilot.json" "$OUT/m_thousands" "$OUT/m_length" --boot 200 --workers 4 --test-phase test2
rm -rf "$OUT/m_thousands" "$OUT/m_length"          # сборка восстанавливается из gha_out/ocdiv2_pilot2_*/ той же командой
