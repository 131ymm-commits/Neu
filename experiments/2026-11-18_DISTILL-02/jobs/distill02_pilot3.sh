#!/bin/bash
# DISTILL-02 «ПРОГРАММА-ГОЛОВЫ»: пилот 3 (совет 74) — те же наборы, что пилот 2, по новым мерам: смесь λ = 1e-3 (записана в код до
# пересчёта), зерно среды (имя, набор), выборки программ в повторах бутстрепа, m2 от одного ящика (m2_max — описательно), разбивка m3;
# мощность правил для PREREG, в том числе Р4Ф по заменителю (перенос X 19–49 → 59–89). Данные — уже собранные, описательно.
set -euo pipefail
OUT="$1"
E=experiments/2026-11-18_DISTILL-02
export HF_HUB_DISABLE_TELEMETRY=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 -c "import numpy, scipy, sklearn, platform; print('версии: python', platform.python_version(), 'numpy', numpy.__version__, 'scipy', scipy.__version__, 'sklearn', sklearn.__version__)" | tee "$OUT/versions.txt"
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
cat > "$OUT/spec3.json" <<SPEC
{"fit": {"T": ["$OUT/m_T_p3", null], "L": ["$OUT/m_L_p3", null],
         "T_low": ["$OUT/m_T_p3", ["T_X19_p3", "T_X29_p3", "T_X39_p3", "T_X49_p3"]]},
 "eval": {"T_test3": ["T", ["$OUT/m_T_t3"], null],
          "L_test3": ["L", ["$OUT/m_L_t3"], null],
          "T_transfer": ["T_low", ["$OUT/m_T_t3"], ["T_X59_p3", "T_X69_p3", "T_X79_p3", "T_X89_p3"]],
          "T_ocdiv3": ["T", ["$OUT/m_T_o3"], null]},
 "R": 20, "B": 200}
SPEC
echo "== пилот 3"
python3 $E/distill02.py pilot3 "$OUT/pilot3.json" "$OUT/spec3.json"
rm -rf "$OUT"/m_*          # сборки восстанавливаются из gha_out/ теми же командами
