#!/bin/bash
# DISTILL-03 «A-НА-B»: тест (PREREG-DISTILL-03.md). Сверка хешей регистрации, тесты кода и замка № 180, сборки построения и test5/new5
# теми же командами, что в анализе DISTILL-02 (jobs/distill02_sum_test.sh), сверка программ с DISTILL-02 (иначе СТОП), матрицы A-на-B на
# 7 средах «тысяч» и 3 средах «длины», вердикты АБ-П-Т, АБ-П-Л, АБ-Ф-Т, АБ-Ф-Л (D > 0 и точное p ≤ 0,0025); new5 — описательно; повтор на
# детерминизм — второй прогон, побайтно без поля seconds. Шаблон лежит в jobs/: пуш регистрации ничего не запускает. Процессор, без ключей.
set -euo pipefail
OUT=$(realpath "$1")
E3=experiments/2026-11-19_DISTILL-03
E2=experiments/2026-11-18_DISTILL-02
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 -c "import numpy, scipy, sklearn, platform; print('версии: python', platform.python_version(), 'numpy', numpy.__version__, 'scipy', scipy.__version__, 'sklearn', sklearn.__version__)" | tee "$OUT/versions.txt"
python3 $E3/prereg_hashes_d3.py --verify --jobs | tee "$OUT/hashes.log"
python3 tools/test_raw_status.py | tee "$OUT/raw_status_test.log" | tail -1
python3 $E3/test_ab.py > "$OUT/tests_full.log" 2>&1 || true
grep -E "^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
grep -q "провалов: 0" "$OUT/tests.log"
T0=$(date +%s)
echo "== сборка построения"
python3 $E2/distill02.py merge2 "$OUT/c_T_o3" test2 thousands gha_out/ocdiv3_test_*
python3 $E2/distill02.py merge4 "$OUT/c_T_p3" pilot3 thousands gha_out/ocdiv4_pilot_*
python3 $E2/distill02.py merge4 "$OUT/c_T_t3" test3 thousands gha_out/ocdiv4_test_*
python3 $E2/distill02.py merge4 "$OUT/c_L_p3" pilot3 length gha_out/ocdiv4_pilot_*
python3 $E2/distill02.py merge4 "$OUT/c_L_t3" test3 length gha_out/ocdiv4_test_*
echo "== сборка теста"
python3 $E2/distill02.py merge_d2 "$OUT/t_T_5" test5 thousands gha_out/distill02_test_*
python3 $E2/distill02.py merge_d2 "$OUT/t_L_5" test5 length gha_out/distill02_test_*
python3 $E2/distill02.py merge_d2 "$OUT/t_T_n" new5 thousands gha_out/distill02_test_*
python3 $E2/distill02.py merge_d2 "$OUT/t_L_n" new5 length gha_out/distill02_test_*
echo "сборки: $(( $(date +%s) - T0 )) с" | tee "$OUT/time.log"
cat > "$OUT/spec.json" <<SPEC
{"construction": {"thousands": ["$OUT/c_T_o3", "$OUT/c_T_p3", "$OUT/c_T_t3"], "length": ["$OUT/c_L_p3", "$OUT/c_L_t3"]},
 "test": {"thousands": ["$OUT/t_T_5"], "length": ["$OUT/t_L_5"]},
 "descriptive": {"thousands": {"new5": ["$OUT/t_T_n"]}, "length": {"new5": ["$OUT/t_L_n"]}},
 "distill02_analysis": "gha_out/distill02_sum_test/analysis.json"}
SPEC
echo "== программы (сверка с DISTILL-02 — иначе СТОП)"
python3 $E3/ab.py fits "$OUT/fits.json" "$OUT/spec.json" | tee "$OUT/fits.log"
python3 -c "import json, sys; f = json.load(open(sys.argv[1]))['families']; ok = all(v and all(v.values()) for fam in f.values() for v in fam['same_as_distill02'].values()); print('программы совпадают с DISTILL-02:', ok); sys.exit(0 if ok else 1)" "$OUT/fits.json" | tee -a "$OUT/fits.log"
echo "== тест"
python3 $E3/ab.py test "$OUT/test.json" "$OUT/spec.json" | tee "$OUT/test.log"
echo "== повтор на детерминизм (побайтно без seconds)"
python3 $E3/ab.py test "$OUT/test2.json" "$OUT/spec.json" > "$OUT/det.log" 2>&1
python3 -c "import json, sys; a, b = (json.load(open(p)) for p in sys.argv[1:3]); [x.pop('seconds') for x in (a, b)]; same = json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True); print('детерминизм:', 'одинаково' if same else 'РАЗЛИЧАЮТСЯ')" "$OUT/test.json" "$OUT/test2.json" | tee "$OUT/det.txt"
echo "всего: $(( $(date +%s) - T0 )) с" | tee -a "$OUT/time.log"
rm -rf "$OUT"/c_* "$OUT"/t_* "$OUT/test2.json"          # сборки восстанавливаются из gha_out/ теми же командами
