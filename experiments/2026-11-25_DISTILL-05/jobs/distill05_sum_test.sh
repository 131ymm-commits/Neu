#!/bin/bash
# DISTILL-05 «ТОКЕН-ОПЕРАТОРЫ»: анализ теста (PREREG-DISTILL-05.md). Сверка хешей регистрации, тесты кода и замка № 180, сборка свежих
# ответов test7, доли масштабов по головам и правила Р1 (по каждой голове) и Р2, сверка повторов извлечения (описательно), повтор анализа
# на детерминизм — побайтно без поля seconds. Шаблон лежит в jobs/: пуш регистрации ничего не запускает. Процессор раннера, без ключей.
set -euo pipefail
OUT=$(realpath "$1")
E5=experiments/2026-11-25_DISTILL-05
E4=experiments/2026-11-19_DISTILL-04
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 -c "import numpy, scipy, platform; print('версии: python', platform.python_version(), 'numpy', numpy.__version__, 'scipy', scipy.__version__)" | tee "$OUT/versions.txt"
python3 $E5/prereg_hashes_d5.py --verify --jobs | tee "$OUT/hashes.log"
python3 tools/test_raw_status.py | tee "$OUT/raw_status_test.log" | tail -1
: > "$OUT/tests_full.log"
for t in $E5/test_scales_d5.py $E5/test_explore_d5.py; do
  echo "== $t" >> "$OUT/tests_full.log"
  python3 "$t" >> "$OUT/tests_full.log" 2>&1 || true
done
grep -E "^== |^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
[ "$(grep -c '^провалов: 0 ' "$OUT/tests.log")" = "2" ] || { echo "СТОП: тесты кода не прошли"; exit 1; }
T0=$(date +%s)
python3 $E5/distill05_extract.py merge "$OUT/t_T_7" test7 thousands gha_out/distill05_test_*
cat > "$OUT/spec.json" <<SPEC
{"sets": {"test7": ["$OUT/t_T_7"]}, "B": 4000}
SPEC
python3 $E5/scales_d5.py test "$OUT/test.json" "$OUT/spec.json" | tee "$OUT/test.log"
python3 -c "
import glob, json, os, sys
sys.path.insert(0, '$E4')
import rep_check_d4 as R
out = {}
for rd in sorted(glob.glob('gha_out/distill05_rep_*')):
    td = rd.replace('distill05_rep_', 'distill05_test_', 1)
    rc, tc = R.cols_of(rd), R.cols_of(td)
    out[os.path.basename(rd)] = {e: R.compare(rc[e], tc[e]) for e in sorted(set(rc) & set(tc))}
json.dump(out, open('$OUT/rep.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('повторы:', {k: {e: {c: v['equal_share'] for c, v in x.items()} for e, x in d.items()} for k, d in out.items()})
" | tee "$OUT/rep.log"
python3 $E5/scales_d5.py test "$OUT/test2.json" "$OUT/spec.json" > "$OUT/det.log" 2>&1
python3 -c "import json, sys; a, b = (json.load(open(p)) for p in sys.argv[1:3]); [x.pop('seconds') for x in (a, b)]; same = json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True); print('детерминизм:', 'одинаково' if same else 'РАЗЛИЧАЮТСЯ')" "$OUT/test.json" "$OUT/test2.json" | tee "$OUT/det.txt"
echo "всего: $(( $(date +%s) - T0 )) с" | tee "$OUT/time.log"
rm -rf "$OUT"/t_* "$OUT/test2.json"          # сборка восстанавливается из gha_out/ той же командой
