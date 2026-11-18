#!/bin/bash
# DISTILL-02 «ПРОГРАММА-ГОЛОВЫ»: пилот на уже собранных ответах семи голов (подсказка только из ID, p = 3) — программы строятся
# по пилоту OCDIV-04 (по семействам; для переноса — по X = 19…49), проверяются на тесте OCDIV-03, тесте OCDIV-04 и на X = 59…89.
# Всё описательно: эти данные разобраны другими мерами; тест DISTILL-02 — свежее извлечение. Процессор раннера, без ключей.
set -euo pipefail
OUT="$1"
E=experiments/2026-11-18_DISTILL-02
export HF_HUB_DISABLE_TELEMETRY=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 tools/test_raw_status.py | tee "$OUT/raw_status_test.log" | tail -1
python3 $E/test_distill02.py > "$OUT/tests_full.log" 2>&1 || true
grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
grep -q "провалов: 0" "$OUT/tests.log"
echo "== сборка"
python3 $E/distill02.py merge4 "$OUT/m_T_p3" pilot3 thousands gha_out/ocdiv4_pilot_*
python3 $E/distill02.py merge4 "$OUT/m_L_p3" pilot3 length gha_out/ocdiv4_pilot_*
python3 $E/distill02.py merge4 "$OUT/m_T_t3" test3 thousands gha_out/ocdiv4_test_*
python3 $E/distill02.py merge4 "$OUT/m_L_t3" test3 length gha_out/ocdiv4_test_*
python3 $E/distill02.py merge2 "$OUT/m_T_o3" test2 thousands gha_out/ocdiv3_test_*
cat > "$OUT/spec.json" <<SPEC
{"fit": {"T": ["$OUT/m_T_p3", null], "L": ["$OUT/m_L_p3", null],
         "T_low": ["$OUT/m_T_p3", ["T_X19_p3", "T_X29_p3", "T_X39_p3", "T_X49_p3"]]},
 "eval": {"ocdiv3_test_T": ["T", ["$OUT/m_T_o3"], null],
          "ocdiv4_test_T": ["T", ["$OUT/m_T_t3"], null],
          "ocdiv4_test_L": ["L", ["$OUT/m_L_t3"], null],
          "transfer_T_highX": ["T_low", ["$OUT/m_T_t3"], ["T_X59_p3", "T_X69_p3", "T_X79_p3", "T_X89_p3"]]},
 "R": 50}
SPEC
echo "== пилот"
python3 $E/distill02.py pilot "$OUT/pilot.json" "$OUT/spec.json"
rm -rf "$OUT"/m_*          # сборки восстанавливаются из gha_out/ теми же командами
