#!/bin/bash
# DISTILL-03 «A-НА-B», пилот (HYPOTHESIS.md 50a2a8f7): программы голов по данным построения DISTILL-02 и сверка с ними
# (formulas в analysis.json DISTILL-02); матрицы 7 × 7 одной среды T_X19_p3 (test5) — описательно; в тест T_X19 не входит.
# Сборки — теми же командами, что в анализе DISTILL-02 (jobs/distill02_sum_test.sh). Процессор раннера, без ключей.
set -euo pipefail
OUT=$(realpath "$1")
E3=experiments/2026-11-19_DISTILL-03
E2=experiments/2026-11-18_DISTILL-02
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 -c "import numpy, platform; print('версии: python', platform.python_version(), 'numpy', numpy.__version__)" | tee "$OUT/versions.txt"
python3 $E3/test_ab.py > "$OUT/tests.log" 2>&1; grep -E "^✓|^✗|провалов" "$OUT/tests.log" | tail -3
grep -q "провалов: 0" "$OUT/tests.log"
T0=$(date +%s)
python3 $E2/distill02.py merge2 "$OUT/c_T_o3" test2 thousands gha_out/ocdiv3_test_*
python3 $E2/distill02.py merge4 "$OUT/c_T_p3" pilot3 thousands gha_out/ocdiv4_pilot_*
python3 $E2/distill02.py merge4 "$OUT/c_T_t3" test3 thousands gha_out/ocdiv4_test_*
python3 $E2/distill02.py merge4 "$OUT/c_L_p3" pilot3 length gha_out/ocdiv4_pilot_*
python3 $E2/distill02.py merge4 "$OUT/c_L_t3" test3 length gha_out/ocdiv4_test_*
python3 $E2/distill02.py merge_d2 "$OUT/t_T_5" test5 thousands gha_out/distill02_test_*
python3 $E2/distill02.py merge_d2 "$OUT/t_L_5" test5 length gha_out/distill02_test_*
echo "сборки: $(( $(date +%s) - T0 )) с" | tee "$OUT/time.log"
cat > "$OUT/spec.json" <<SPEC
{"construction": {"thousands": ["$OUT/c_T_o3", "$OUT/c_T_p3", "$OUT/c_T_t3"], "length": ["$OUT/c_L_p3", "$OUT/c_L_t3"]},
 "test": {"thousands": ["$OUT/t_T_5"], "length": ["$OUT/t_L_5"]},
 "distill02_analysis": "gha_out/distill02_sum_test/analysis.json"}
SPEC
python3 $E3/ab.py fits "$OUT/fits.json" "$OUT/spec.json" | tee "$OUT/fits.log"
python3 $E3/ab.py pilot "$OUT/pilot.json" "$OUT/spec.json" | tee "$OUT/pilot.log"
echo "всего: $(( $(date +%s) - T0 )) с" | tee -a "$OUT/time.log"
rm -rf "$OUT"/c_* "$OUT"/t_*          # сборки восстанавливаются из gha_out/ теми же командами
# перезапуск пилота после ERRORS № 224 (18:32 UTC)
