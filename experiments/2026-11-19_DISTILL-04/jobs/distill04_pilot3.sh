#!/bin/bash
# DISTILL-04 «ПРОЧИЕ»: пилот 3 (совет 78, п. 6: П1-Т пилота в обеих версиях нормировки — добавлена описательная мера m_M_sym; прочие меры должны совпасть с пилотом 2 побайтно) (описательно, до PREREG) — программы по построению DISTILL-02, каталог операторов по правилу CATALOG_MIN
# на построении, меры М против нуля-Т того же размера на уже виденных test5/new5 DISTILL-02 (бутстреп B = 200), мощность П1 и П2 для
# теста на 8 новых средах «тысяч». Тест DISTILL-04 — на новых ответах. Процессор раннера, без ключей.
set -euo pipefail
OUT=$(realpath "$1")
E4=experiments/2026-11-19_DISTILL-04
E2=experiments/2026-11-18_DISTILL-02
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 -c "import numpy, scipy, platform; print('версии: python', platform.python_version(), 'numpy', numpy.__version__, 'scipy', scipy.__version__)" | tee "$OUT/versions.txt"
python3 $E4/test_prog_m.py > "$OUT/tests.log" 2>&1 || true
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
echo "сборки: $(( $(date +%s) - T0 )) с" | tee "$OUT/time.log"
cat > "$OUT/spec.json" <<SPEC
{"construction": {"thousands": ["$OUT/c_T_o3", "$OUT/c_T_p3", "$OUT/c_T_t3"], "length": ["$OUT/c_L_p3", "$OUT/c_L_t3"]},
 "eval": {"test5_thousands": {"family": "thousands", "dirs": ["$OUT/t_T_5"]}, "test5_length": {"family": "length", "dirs": ["$OUT/t_L_5"]},
          "new5_thousands": {"family": "thousands", "dirs": ["$OUT/t_T_n"]}, "new5_length": {"family": "length", "dirs": ["$OUT/t_L_n"]}},
 "B": 200, "seed": 9940000, "m_test": {"thousands": 8, "length": 1}}
SPEC
python3 $E4/pilot_d4.py "$OUT/pilot.json" "$OUT/spec.json" | tee "$OUT/pilot.log"
echo "всего: $(( $(date +%s) - T0 )) с" | tee -a "$OUT/time.log"
rm -rf "$OUT"/c_* "$OUT"/t_*          # сборки восстанавливаются из gha_out/ теми же командами
