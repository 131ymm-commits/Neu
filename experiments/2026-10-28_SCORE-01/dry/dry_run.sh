#!/bin/bash
# SCORE-01, сухой прогон всей цепочки на заглушках (LENSES-1, L2-2; LENSES-1b, N15): четыре этапа как в тесте — Opus один вызов
# на клетку, Haiku два; основная выборка и повтор. Головы не вызываются. Запуск из папки опыта: bash dry/dry_run.sh
#   ветка A: потери и задачи без записи (Opus main — «не показано (потери)»), флаг контекста на rep_haiku (копия проверки
#            загрязнённого пилота 2) → чтение «не показано (контекст)»;
#   ветка B: Opus без потерь → статусы «установлено» и «подтверждено (повторено; причина не проверялась)»; у Haiku main навык
#            второго вызова сдвинут → A/A не проходит → SA_haiku читается «не показано (A/A …)»;
#   сверка хешей и покрытия — в копии опыта (prereg_hashes.json пишется только там; временные файлы — там же и удаляются).
set -euo pipefail
cd "$(dirname "$0")/.."
EXP=$(pwd)
STAGES=main_opus,rep_opus,main_haiku,rep_haiku
mkdir -p dry/evals dry/evals_b dry/ctx dry/ctx_ok
# 0) проверки контекста этапов — копии калибровки на пилотах (run/pilot_ctx_stage_*.json): чистый пилот 3, загрязнённый пилот 2
cp run/pilot_ctx_stage_pilot3_opus.json dry/ctx/ctx_main_opus.json
cp run/pilot_ctx_stage_pilot3_opus.json dry/ctx/ctx_rep_opus.json
cp run/pilot_ctx_stage_pilot3_haiku.json dry/ctx/ctx_main_haiku.json
cp run/pilot_ctx_stage_pilot2_haiku.json dry/ctx/ctx_rep_haiku.json
for st in main_opus rep_opus; do cp run/pilot_ctx_stage_pilot3_opus.json dry/ctx_ok/ctx_$st.json; done
for st in main_haiku rep_haiku; do cp run/pilot_ctx_stage_pilot3_haiku.json dry/ctx_ok/ctx_$st.json; done
# 1) заглушки. Ветка A: Opus — навык LOG = WIN, NONE ниже; в основной выборке Opus 15 задач без записи; Haiku — два повтора
python3 dry/make_stub.py main LOG,WIN,NONE 0.45,0.45,0.0 dry/stub_main_opus.jsonl 0.03 11 1 15
python3 dry/make_stub.py rep LOG,WIN,NONE 0.45,0.45,0.0 dry/stub_rep_opus.jsonl 0.03 12 1 0
python3 dry/make_stub.py main LOG,WIN,NONE 0.3,0.3,0.5 dry/stub_main_haiku.jsonl 0.03 13 2 0
python3 dry/make_stub.py rep LOG,WIN,NONE 0.3,0.3,0.5 dry/stub_rep_haiku.jsonl 0.03 14 2 0
# ветка B: Opus без потерь; Haiku main — навык второго вызова ниже на 0,6
python3 dry/make_stub.py main LOG,WIN,NONE 0.45,0.45,0.0 dry/stub_b_main_opus.jsonl 0.0 21 1 0
python3 dry/make_stub.py rep LOG,WIN,NONE 0.45,0.45,0.0 dry/stub_b_rep_opus.jsonl 0.0 22 1 0
python3 dry/make_stub.py main LOG,WIN,NONE 0.3,0.3,0.5 dry/stub_b_main_haiku.jsonl 0.03 23 2 0 -0.6
python3 dry/make_stub.py rep LOG,WIN,NONE 0.3,0.3,0.5 dry/stub_b_rep_haiku.jsonl 0.03 24 2 0
# 2) меры (метки по 4000 реализациям) → dry/evals*/<этап>.json
mk() {  # $1 — этап, $2 — заглушка, $3 — папка evals
  local sample=${1%%_*}
  python3 score01.py metrics dry_tmp_$1 $sample $2 half4 > /dev/null
  python3 - "$1" "$3" <<'EOF'
import json, sys, os
st, d = sys.argv[1], sys.argv[2]
E = json.load(open(f'evals/dry_tmp_{st}.json')); E['stage'] = st
json.dump(E, open(f'{d}/{st}.json', 'w'), ensure_ascii=False, indent=1); os.remove(f'evals/dry_tmp_{st}.json')
EOF
}
for st in main_opus rep_opus main_haiku rep_haiku; do
  mk $st dry/stub_$st.jsonl dry/evals
  mk $st dry/stub_b_$st.jsonl dry/evals_b
done
# 3) анализ без сверки хешей (в рабочей папке опыта)
python3 analyze_score01.py --stages $STAGES --evals dry/evals --ctx-json dry/ctx --out dry/analysis_dry.json --no-check | tee dry/dry_analysis.log
python3 analyze_score01.py --stages $STAGES --evals dry/evals_b --ctx-json dry/ctx_ok --out dry/analysis_dry_b.json --no-check | tee dry/dry_analysis_b.log
# 4) сверка хешей и покрытия — в копии опыта: хеши пишутся там, задания берутся настоящие (jobs/)
TMP=$(mktemp -d)
mkdir -p "$TMP/experiments" "$TMP/tools"
cp -r "$EXP" "$TMP/experiments/2026-10-28_SCORE-01"
cp -r "$EXP/../2026-10-07_SELECT-01" "$TMP/experiments/2026-10-07_SELECT-01"
cp "$EXP/../../tools/run_sealed2.py" "$TMP/tools/"
cd "$TMP/experiments/2026-10-28_SCORE-01"
for st in main_opus rep_opus main_haiku rep_haiku; do cp dry/evals/$st.json evals/$st.json; done
python3 prereg_hashes.py > /dev/null
python3 analyze_score01.py --stages $STAGES --ctx-json dry/ctx --out "$TMP/score01_dry_check.json" 2>&1 | grep -E "хеши|заданий|статус|контекст" | tee "$EXP/dry/dry_check.log"
cd "$EXP"; rm -rf "$TMP"
echo "сухой прогон: готово"
