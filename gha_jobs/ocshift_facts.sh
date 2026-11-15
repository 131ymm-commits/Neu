#!/bin/bash
# OCSHIFT-01: производные числа отчёта из анализа теста (сборка чисел; вердиктов не меняет). GitHub Actions — слово автора
# 15.11.2026: все счёты по данным опытов — на сторонних площадках. Запуск — после результатов gha_jobs/ocshift_test.sh.
set -euo pipefail
OUT="$1"
E=experiments/2026-11-15_OCSHIFT-01
python3 -m pip install -q numpy==2.5.3
python3 $E/facts_ocshift.py gha_out/ocshift_test/analysis.json "$OUT/facts_ocshift.json" > "$OUT/facts_stdout.txt"
python3 -c "import json; d = json.load(open('$OUT/facts_ocshift.json')); print('готово: ключей', len(d), '| вердикты', d['verdicts'])"
