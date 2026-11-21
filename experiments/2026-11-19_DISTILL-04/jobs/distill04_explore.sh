#!/bin/bash
# DISTILL-04 «ПРОЧИЕ» (HYPOTHESIS.md 11ae9f8c): разведка, описательно, до PREREG — (1) операторы «прочих» ошибок на построении
# (OCDIV-03/04) и на уже виденных test5/new5 DISTILL-02, покрытие операторами и таблицей частот; (2) нарезка чисел токенизаторами
# семи голов (только токенизаторы, без весов). Новых ответов голов нет. Процессор раннера, без ключей.
set -euo pipefail
OUT=$(realpath "$1")
E4=experiments/2026-11-19_DISTILL-04
E2=experiments/2026-11-18_DISTILL-02
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0 transformers==5.20.2
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 -c "import numpy, transformers, platform; print('версии: python', platform.python_version(), 'numpy', numpy.__version__, 'transformers', transformers.__version__)" | tee "$OUT/versions.txt"
python3 $E4/test_explore_d4.py > "$OUT/tests.log" 2>&1; grep -E "^✗|провалов" "$OUT/tests.log" | tail -3
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
 "sets": {"test5_thousands": {"family": "thousands", "dirs": ["$OUT/t_T_5"]}, "test5_length": {"family": "length", "dirs": ["$OUT/t_L_5"]},
          "new5_thousands": {"family": "thousands", "dirs": ["$OUT/t_T_n"]}, "new5_length": {"family": "length", "dirs": ["$OUT/t_L_n"]}}}
SPEC
python3 $E4/explore_d4.py "$OUT/explore.json" "$OUT/spec.json" | tee "$OUT/explore.log"
python3 $E4/tokenizers_d4.py "$OUT/tokenizers.json" | tee "$OUT/tokenizers.log"
echo "всего: $(( $(date +%s) - T0 )) с" | tee -a "$OUT/time.log"
rm -rf "$OUT"/c_* "$OUT"/t_*          # сборки восстанавливаются из gha_out/ теми же командами
