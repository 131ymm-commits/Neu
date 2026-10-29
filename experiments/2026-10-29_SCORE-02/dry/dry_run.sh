#!/bin/bash
# SCORE-02, сухой прогон цепочки на заглушках (головы не вызываются): заглушка → score02.py metrics → analyze_score02.py --dry →
# сверка с ожиданиями, записанными до запуска (dry/expect.json, dry/check_expect.py).
# Ветки (dry/make_stub.py): A — согласие несёт сведения (logit a 1, c 0,3, s 1); N0 — пять одинаковых вызовов при точности около 0,6
# (logit a 0,3, c 1, s 0; нуль: у согласия один уровень); N2 — почти независимые вызовы при точности около 0,6 (logit a 0,3, c 0,3, s 1);
# E — согласие хуже вызова и на равной грубости (belief a 0,65, c 0,85, s 1,5); C — как A, потери 15 %; D — как A, флаг контекста в rep_haiku.
# Проверка контекста в сухом прогоне — из dry/ctx_<этап>.json (заглушка: флаг нет / да). Ветка B (вызовы одинаковы при точности 1,0,
# AUC не определён) прежнего прогона заменена на N0 (LENSES-1, L2-1).
#   bash dry/dry_run.sh   (из папки опыта)
set -euo pipefail
cd "$(dirname "$0")/.."
ok_ctx () { for st in main_opus rep_opus main_haiku rep_haiku; do echo '{"flag": false, "why": [], "n": 1}' > dry/ctx_$st.json; done; }
run () {  # $1 — ветка; $2.. — параметры заглушки a c s потери режим
  for st in main_opus rep_opus main_haiku rep_haiku; do
    smp=${st%%_*}
    python3 dry/make_stub.py $smp dry/stub_$1_$st.jsonl $2 $3 $4 $5 ${#st} 5 0 $6 > /dev/null
    python3 score02.py metrics $st $smp dry/stub_$1_$st.jsonl 5 dry/evals > /dev/null
  done
  python3 analyze_score02.py --dry > dry/dry_$1.log
  cp dry/analysis_score02.json dry/analysis_$1.json
  echo "== ветка $1"; grep -E "сводный|статус" dry/dry_$1.log
}
rm -f dry/stub_B_*.jsonl dry/dry_B.log dry/analysis_B.json
ok_ctx
run A 1.0 0.3 1.0 0.0 logit
run N0 0.3 1.0 0.0 0.0 logit
run N2 0.3 0.3 1.0 0.0 logit
run E 0.65 0.85 1.5 0.0 belief
run C 1.0 0.3 1.0 0.15 logit
echo '{"flag": true, "why": ["заглушка: вход выше линии"], "n": 1}' > dry/ctx_rep_haiku.json
run D 1.0 0.3 1.0 0.0 logit
ok_ctx
python3 dry/check_expect.py
