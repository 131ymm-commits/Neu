#!/bin/bash
# SCORE-01, сухой прогон всей цепочки на заглушках (LENSES-1, L2-2): четыре этапа как в тесте — Opus один вызов на клетку,
# Haiku два; основная выборка и повтор; потери и задачи без записи; сверка хешей и покрытия — в копии опыта
# (prereg_hashes.json пишется только там). Головы не вызываются. Запуск из папки опыта: bash dry/dry_run.sh
set -euo pipefail
cd "$(dirname "$0")/.."
EXP=$(pwd)
mkdir -p dry/evals
# 1) заглушки: Opus — навык LOG = WIN, NONE ниже; Haiku — два повтора; в основной выборке Opus 15 задач без записи (должно дать «не показано (потери)»)
python3 dry/make_stub.py main LOG,WIN,NONE 0.45,0.45,0.0 dry/stub_main_opus.jsonl 0.03 11 1 15
python3 dry/make_stub.py rep LOG,WIN,NONE 0.45,0.45,0.0 dry/stub_rep_opus.jsonl 0.03 12 1 0
python3 dry/make_stub.py main LOG,WIN,NONE 0.3,0.3,0.5 dry/stub_main_haiku.jsonl 0.03 13 2 0
python3 dry/make_stub.py rep LOG,WIN,NONE 0.3,0.3,0.5 dry/stub_rep_haiku.jsonl 0.03 14 2 0
# 2) меры (метки по 4000 реализациям) → dry/evals/<этап>.json
for st in main_opus rep_opus main_haiku rep_haiku; do
  sample=${st%%_*}
  python3 score01.py metrics dry_tmp_$st $sample dry/stub_$st.jsonl half4 > /dev/null
  python3 - "$st" <<'EOF'
import json, sys, os
st = sys.argv[1]
E = json.load(open(f'evals/dry_tmp_{st}.json')); E['stage'] = st
json.dump(E, open(f'dry/evals/{st}.json', 'w'), ensure_ascii=False, indent=1); os.remove(f'evals/dry_tmp_{st}.json')
EOF
done
# 3) анализ без сверки хешей (в рабочей папке опыта)
python3 analyze_score01.py --stages main_opus,rep_opus,main_haiku,rep_haiku --evals dry/evals --out dry/analysis_dry.json --no-check | tee dry/dry_analysis.log
# 4) сверка хешей и покрытия — в копии опыта: хеши пишутся там, задания берутся настоящие
TMP=$(mktemp -d)
mkdir -p "$TMP/experiments" "$TMP/tools"
cp -r "$EXP" "$TMP/experiments/2026-10-28_SCORE-01"
cp -r "$EXP/../2026-10-07_SELECT-01" "$TMP/experiments/2026-10-07_SELECT-01"
cp "$EXP/../../tools/run_sealed2.py" "$TMP/tools/"
cd "$TMP/experiments/2026-10-28_SCORE-01"
for st in main_opus rep_opus main_haiku rep_haiku; do cp dry/evals/$st.json evals/$st.json; done
python3 prereg_hashes.py > /dev/null
python3 analyze_score01.py --stages main_opus,rep_opus,main_haiku,rep_haiku --out /tmp/score01_dry_check.json 2>&1 | grep -E "хеши|заданий|статус" | tee "$EXP/dry/dry_check.log"
cd "$EXP"; rm -rf "$TMP"
echo "сухой прогон: готово"
