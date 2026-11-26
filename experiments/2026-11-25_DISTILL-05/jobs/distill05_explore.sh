#!/bin/bash
# DISTILL-05 «ТОКЕН-ОПЕРАТОРЫ»: разведка (описательно, до PREREG) — масштаб «прочих» смещений голов по длине суммы на уже виденных ответах:
# построение (тест OCDIV-03, пилот и тест OCDIV-04), test5/new5 DISTILL-02, test6/test6L DISTILL-04. Процессор раннера, без ключей.
set -euo pipefail
OUT=$(realpath "$1")
E5=experiments/2026-11-25_DISTILL-05
E4=experiments/2026-11-19_DISTILL-04
E2=experiments/2026-11-18_DISTILL-02
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 -c "import numpy, scipy, platform; print('версии: python', platform.python_version(), 'numpy', numpy.__version__, 'scipy', scipy.__version__)" | tee "$OUT/versions.txt"
python3 $E5/test_explore_d5.py > "$OUT/tests.log" 2>&1 || true
grep -E "^✗|провалов" "$OUT/tests.log" | tail -3
grep -q "провалов: 0" "$OUT/tests.log"
T0=$(date +%s)
python3 $E2/distill02.py merge2 "$OUT/c_T_o3" test2 thousands gha_out/ocdiv3_test_*
python3 $E2/distill02.py merge4 "$OUT/c_T_p3" pilot3 thousands gha_out/ocdiv4_pilot_*
python3 $E2/distill02.py merge4 "$OUT/c_T_t3" test3 thousands gha_out/ocdiv4_test_*
python3 $E2/distill02.py merge4 "$OUT/c_L_p3" pilot3 length gha_out/ocdiv4_pilot_*
python3 $E2/distill02.py merge4 "$OUT/c_L_t3" test3 length gha_out/ocdiv4_test_*
python3 $E2/distill02.py merge_d2 "$OUT/t_T_5" test5 thousands gha_out/distill02_test_*
python3 $E2/distill02.py merge_d2 "$OUT/t_L_5" test5 length gha_out/distill02_test_*
python3 $E2/distill02.py merge_d2 "$OUT/t_T_n" new5 thousands gha_out/distill02_test_*
python3 $E2/distill02.py merge_d2 "$OUT/t_L_n" new5 length gha_out/distill02_test_*
python3 -c "import glob, sys; sys.path.insert(0, '$E4'); import distill04_extract as X; X.merge_d4('$OUT/t_T_6', 'test6', 'thousands', sorted(glob.glob('gha_out/distill04_test_*')))"
python3 -c "import glob, sys; sys.path.insert(0, '$E4'); import distill04_extract as X; X.merge_d4('$OUT/t_L_6', 'test6L', 'length', sorted(glob.glob('gha_out/distill04_test_*')))"
echo "сборки: $(( $(date +%s) - T0 )) с" | tee "$OUT/time.log"
cat > "$OUT/spec.json" <<SPEC
{"sets": {"построение": ["$OUT/c_T_o3", "$OUT/c_T_p3", "$OUT/c_T_t3", "$OUT/c_L_p3", "$OUT/c_L_t3"],
          "test5": ["$OUT/t_T_5", "$OUT/t_L_5"], "new5": ["$OUT/t_T_n", "$OUT/t_L_n"], "test6": ["$OUT/t_T_6", "$OUT/t_L_6"]}}
SPEC
python3 $E5/explore_d5.py "$OUT/explore.json" "$OUT/spec.json" | tee "$OUT/explore.log"
echo "всего: $(( $(date +%s) - T0 )) с" | tee -a "$OUT/time.log"
rm -rf "$OUT"/c_* "$OUT"/t_*          # сборки восстанавливаются из gha_out/ теми же командами
