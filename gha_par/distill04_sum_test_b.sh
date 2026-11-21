#!/bin/bash
# ОТСТУПЛЕНИЕ (DEVIATIONS.md, ERRORS № 233): повтор задания distill04_sum_test после сбоя. Отличие от шаблона регистрации — только две строки
# сборки test6/test6L: зарегистрированная merge_d4 вызывается напрямую, её возвращаемое значение отбрасывается (CLI main возвращал словарь
# итога → sys.exit печатал его и выходил с кодом 1). Зарегистрированные файлы не меняются; сверка хешей — та же.
# DISTILL-04 «ПРОЧИЕ»: анализ теста (PREREG-DISTILL-04.md). Сверка хешей регистрации, тесты кода и замка № 180, сборки построения (теми же
# командами, что в анализе DISTILL-02 и тесте DISTILL-03) и свежих ответов test6/test6L (distill04_extract.py merge), сверка программ с
# DISTILL-02 (замок а совета 76, иначе СТОП), правила П1-Т (решающее), П1МТ-Т и П2-Т (описательно), повтор A-на-B на 8 новых средах
# (АБ-П-Т6, АБ-Ф-Т6), «длина» L_X9999 описательно, сверка повторов извлечения (описательно), повтор анализа на детерминизм — побайтно
# без поля seconds. Шаблон лежит в jobs/: пуш регистрации ничего не запускает. Процессор раннера, без ключей.
set -euo pipefail
OUT=$(realpath "$1")
E4=experiments/2026-11-19_DISTILL-04
E3=experiments/2026-11-19_DISTILL-03
E2=experiments/2026-11-18_DISTILL-02
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 -c "import numpy, scipy, sklearn, platform; print('версии: python', platform.python_version(), 'numpy', numpy.__version__, 'scipy', scipy.__version__, 'sklearn', sklearn.__version__)" | tee "$OUT/versions.txt"
python3 $E4/prereg_hashes_d4.py --verify --jobs | tee "$OUT/hashes.log"
python3 tools/test_raw_status.py | tee "$OUT/raw_status_test.log" | tail -1
: > "$OUT/tests_full.log"
for t in $E4/test_prog_m.py $E4/test_explore_d4.py $E4/test_extract_d4.py $E4/test_analysis_d4.py $E3/test_ab.py; do
  echo "== $t" >> "$OUT/tests_full.log"
  python3 "$t" >> "$OUT/tests_full.log" 2>&1 || true
done
grep -E "^== |^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
[ "$(grep -c '^провалов: 0 ' "$OUT/tests.log")" = "5" ] || { echo "СТОП: тесты кода не прошли"; exit 1; }
T0=$(date +%s)
echo "== сборка построения"
python3 $E2/distill02.py merge2 "$OUT/c_T_o3" test2 thousands gha_out/ocdiv3_test_*
python3 $E2/distill02.py merge4 "$OUT/c_T_p3" pilot3 thousands gha_out/ocdiv4_pilot_*
python3 $E2/distill02.py merge4 "$OUT/c_T_t3" test3 thousands gha_out/ocdiv4_test_*
python3 $E2/distill02.py merge4 "$OUT/c_L_p3" pilot3 length gha_out/ocdiv4_pilot_*
python3 $E2/distill02.py merge4 "$OUT/c_L_t3" test3 length gha_out/ocdiv4_test_*
echo "== сборка свежих ответов теста"
python3 -c "import glob, sys; sys.path.insert(0, '$E4'); import distill04_extract as X; X.merge_d4('$OUT/t_T_6', 'test6', 'thousands', sorted(glob.glob('gha_out/distill04_test_*')))"
python3 -c "import glob, sys; sys.path.insert(0, '$E4'); import distill04_extract as X; X.merge_d4('$OUT/t_L_6', 'test6L', 'length', sorted(glob.glob('gha_out/distill04_test_*')))"
echo "сборки: $(( $(date +%s) - T0 )) с" | tee "$OUT/time.log"
cat > "$OUT/spec.json" <<SPEC
{"construction": {"thousands": ["$OUT/c_T_o3", "$OUT/c_T_p3", "$OUT/c_T_t3"], "length": ["$OUT/c_L_p3", "$OUT/c_L_t3"]},
 "test": {"thousands": ["$OUT/t_T_6"]},
 "descriptive": {"length": ["$OUT/t_L_6"]},
 "distill02_analysis": "gha_out/distill02_sum_test/analysis.json"}
SPEC
echo "== программы (сверка с DISTILL-02 — иначе СТОП; совет 76, замок а)"
python3 $E3/ab.py fits "$OUT/fits.json" "$OUT/spec.json" | tee "$OUT/fits.log"
python3 $E3/ab.py checkfits "$OUT/fits.json" | tee -a "$OUT/fits.log"
echo "== тест"
python3 $E4/test_d4.py "$OUT/test.json" "$OUT/spec.json" | tee "$OUT/test.log"
echo "== повторы извлечения (описательно)"
python3 $E4/rep_check_d4.py "$OUT/rep.json" | tee "$OUT/rep.log"
echo "== повтор анализа на детерминизм (побайтно без seconds)"
python3 $E4/test_d4.py "$OUT/test2.json" "$OUT/spec.json" > "$OUT/det.log" 2>&1
python3 -c "import json, sys; a, b = (json.load(open(p)) for p in sys.argv[1:3]); [x.pop('seconds') for x in (a, b)]; same = json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True); print('детерминизм:', 'одинаково' if same else 'РАЗЛИЧАЮТСЯ')" "$OUT/test.json" "$OUT/test2.json" | tee "$OUT/det.txt"
echo "всего: $(( $(date +%s) - T0 )) с" | tee -a "$OUT/time.log"
rm -rf "$OUT"/c_* "$OUT"/t_* "$OUT/test2.json"          # сборки восстанавливаются из gha_out/ теми же командами
