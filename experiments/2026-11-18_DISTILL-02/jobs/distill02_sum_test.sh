#!/bin/bash
# DISTILL-02 «ПРОГРАММА-ГОЛОВЫ»: анализ теста — после вывода всех 105 заданий и 3 повторов; сверка хешей регистрации, тесты кода и замка № 180, сборка построения и свежих фаз, правила и описательное (B = 4000, R = 20, 4 процесса, частичный json по средам); повтор на детерминизм — 2 среды, B = 200, побайтно (совет 74). Файл создан make_jobs_d2.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-18_DISTILL-02
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1          # совет 74, п. 8: детерминизм бустинга и BLAS
python3 -c "import numpy, scipy, sklearn, platform; print('версии: python', platform.python_version(), 'numpy', numpy.__version__, 'scipy', scipy.__version__, 'sklearn', sklearn.__version__)" | tee "$OUT/versions.txt"
python3 $E/prereg_hashes_d2.py --verify --jobs
python3 tools/test_raw_status.py | tee "$OUT/raw_status_test.log" | tail -1
python3 $E/test_distill02.py > "$OUT/tests_full.log" 2>&1 || true
grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
grep -q "провалов: 0" "$OUT/tests.log"
echo "== сборка построения"
python3 $E/distill02.py merge2 "$OUT/c_T_o3" test2 thousands gha_out/ocdiv3_test_*
python3 $E/distill02.py merge4 "$OUT/c_T_p3" pilot3 thousands gha_out/ocdiv4_pilot_*
python3 $E/distill02.py merge4 "$OUT/c_T_t3" test3 thousands gha_out/ocdiv4_test_*
python3 $E/distill02.py merge4 "$OUT/c_L_p3" pilot3 length gha_out/ocdiv4_pilot_*
python3 $E/distill02.py merge4 "$OUT/c_L_t3" test3 length gha_out/ocdiv4_test_*
echo "== сборка теста"
python3 $E/distill02.py merge_d2 "$OUT/t_T_5" test5 thousands gha_out/distill02_test_*
python3 $E/distill02.py merge_d2 "$OUT/t_L_5" test5 length gha_out/distill02_test_*
python3 $E/distill02.py merge_d2 "$OUT/t_T_n" new5 thousands gha_out/distill02_test_*
python3 $E/distill02.py merge_d2 "$OUT/t_L_n" new5 length gha_out/distill02_test_*
cat > "$OUT/spec_test.json" <<SPEC
{"construction": {"thousands": ["$OUT/c_T_o3", "$OUT/c_T_p3", "$OUT/c_T_t3"], "length": ["$OUT/c_L_p3", "$OUT/c_L_t3"]},
 "test": {"test5": ["$OUT/t_T_5", "$OUT/t_L_5"], "new5": ["$OUT/t_T_n", "$OUT/t_L_n"]},
 "B": 4000, "R": 20, "workers": 4, "part_dir": "$OUT/envs"}
SPEC
echo "== анализ"
timeout 180m python3 $E/distill02.py test "$OUT/analysis.json" "$OUT/spec_test.json"
echo "== повтор на детерминизм (2 среды, B = 200, дважды; побайтно)"
python3 -c "import json, sys; s = json.load(open(sys.argv[1])); s.update(B=200, only=['T_X19_p3', 'L_X9_p3'], no_time=True, workers=1); s.pop('part_dir'); json.dump(s, open(sys.argv[2], 'w'))" "$OUT/spec_test.json" "$OUT/spec_det.json"
python3 $E/distill02.py test "$OUT/det1.json" "$OUT/spec_det.json" > "$OUT/det.log" 2>&1
python3 $E/distill02.py test "$OUT/det2.json" "$OUT/spec_det.json" >> "$OUT/det.log" 2>&1
(cmp -s "$OUT/det1.json" "$OUT/det2.json" && echo "детерминизм: побайтно одинаково" || echo "детерминизм: РАЗЛИЧАЮТСЯ") | tee "$OUT/det.txt"
echo "== прибор"; python3 experiments/2026-11-17_OCDIV-02/trunc_check.py "$OUT/trunc.json" "gha_out/distill02_test_*/answers_*.json" | tail -3
rm -rf "$OUT"/c_* "$OUT"/t_*          # сборки восстанавливаются из gha_out/ теми же командами; envs/ — для продолжения
