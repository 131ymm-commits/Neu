#!/bin/bash
# SPECTRUM-02 «показатель»: основной прогон на GitHub Actions (PREREG-SPECTRUM-02.md §10; файл входит в хеши регистрации).
# Вызывается обёрткой gha_jobs/spectrum02.sh из корня репозитория: bash experiments/2026-11-14_SPECTRUM-02/gha_spectrum02.sh <папка вывода>
# DRY=1 — сухой прогон цепочки: вместо обучения — заглушка «true» с зёрнами теста (совет 50, п. 6).
# При расхождении хешей, провале тестов или ошибке анализа задание останавливается (set -e, pipefail).
set -euo pipefail
OUT="$(realpath "$1")"
mkdir -p "$OUT"
cd "$(dirname "$0")"
if [ "${DRY:-0}" != "1" ]; then python3 -m pip install -q -r requirements.txt; fi
python3 -c "import sys, os, numpy, sklearn, scipy, joblib; print('python', sys.version.split()[0], '| процессоров', os.cpu_count(), '| numpy', numpy.__version__, '| sklearn', sklearn.__version__, '| scipy', scipy.__version__, '| joblib', joblib.__version__)" | tee "$OUT/env.txt"
python3 prereg_hashes.py --verify | tee "$OUT/verify.txt"
if [ "${DRY:-0}" = "1" ]; then
  echo "СУХОЙ ПРОГОН: заглушка вместо обучения" | tee "$OUT/run.log"
  python3 dry_spectrum02.py --emit true run_dry/results.json | tee -a "$OUT/run.log"
  RES=run_dry/results.json
else
  python3 test_spectrum02.py | tee "$OUT/test.txt"
  python3 spectrum02.py --run --jobs 4 | tee "$OUT/run.log"
  RES=run/results.json
fi
sha256sum "$RES" | tee "$OUT/results.json.sha256"
gzip -9 -c "$RES" > "$OUT/results.json.gz"
python3 analyze_spectrum02.py "$RES" "$OUT/analysis.json" --test | tee "$OUT/analysis.log"
