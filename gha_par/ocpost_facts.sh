#!/bin/bash
# OCPOST-01: производные числа отчёта и вес опоры по PREREG §10 (сборка чисел; вердиктов не меняет). Сторонняя площадка —
# слово автора 15.11.2026. Запуск — после того как в ветке лежат gha_out/ocpost_test/analysis.json и gha_out/ocpost_tail_sum/tail.json.
# facts_ocpost.py не входит в хеши регистрации (написан после неё, до данных теста: коммит 7a005436); его sha256 — в логе.
set -euo pipefail
OUT="$1"
E=experiments/2026-11-15_OCPOST-01
python3 -m pip install -q numpy==2.5.3
test -s gha_out/ocpost_test/analysis.json && test -s gha_out/ocpost_tail_sum/tail.json
sha256sum $E/facts_ocpost.py $E/expect_ocpost.json gha_out/ocpost_test/analysis.json gha_out/ocpost_tail_sum/tail.json
python3 $E/facts_ocpost.py gha_out/ocpost_test/analysis.json gha_out/ocpost_tail_sum/tail.json "$OUT/facts_ocpost.json" > "$OUT/facts_stdout.txt"
python3 -c "import json; d = json.load(open('$OUT/facts_ocpost.json')); print('готово: Т', d['tail_verdict'], '| вес, бит', {k: round(v['bits'], 2) for k, v in d['weights'].items()})"
