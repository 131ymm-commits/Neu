#!/bin/bash
# SCORE-02, сухой прогон цепочки на заглушках (головы не вызываются): заглушка → score02.py metrics → analyze_score02.py --dry.
# Ветки: A — согласие несёт сведения (a 1, c 0,3, s 1); B — вызовы одинаковы (s 0: согласие не несёт сведений); C — потери 15 %;
# D — флаг контекста. Проверка контекста в сухом прогоне — из dry/ctx_<этап>.json (заглушка: флаг нет / да).
#   bash dry/dry_run.sh   (из папки опыта)
set -euo pipefail
cd "$(dirname "$0")/.."
ok_ctx () { for st in main_opus rep_opus main_haiku rep_haiku; do echo '{"flag": false, "why": [], "n": 1}' > dry/ctx_$st.json; done; }
run () {  # $1 — ветка; $2.. — параметры заглушки a c s потери
  for st in main_opus rep_opus main_haiku rep_haiku; do
    smp=${st%%_*}
    python3 dry/make_stub.py $smp dry/stub_$1_$st.jsonl $2 $3 $4 $5 ${#st} 5 0 > /dev/null
    python3 score02.py metrics $st $smp dry/stub_$1_$st.jsonl 5 dry/evals > /dev/null
  done
  python3 analyze_score02.py --dry > dry/dry_$1.log
  cp dry/analysis_score02.json dry/analysis_$1.json
  echo "== ветка $1"; grep -E "сводный|статус" dry/dry_$1.log
}
ok_ctx
run A 1.0 0.3 1.0 0.0
run B 1.0 0.3 0.0 0.0
run C 1.0 0.3 1.0 0.15
echo '{"flag": true, "why": ["заглушка: вход выше линии"], "n": 1}' > dry/ctx_rep_haiku.json
run D 1.0 0.3 1.0 0.0
ok_ctx
