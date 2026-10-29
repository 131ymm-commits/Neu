#!/bin/bash
# SCORE-02, сухой прогон цепочки на заглушках (головы не вызываются): заглушка → score02.py metrics → analyze_score02.py --dry →
# сверка с ожиданиями, записанными до запуска (второй прогон, после LENSES-2: dry/expect2.json → dry/check_expect2.log;
# первый — dry/expect.json, коммит 2c295e9, его журналы — в истории git, 82a5d09).
# Ветки (dry/make_stub.py; зерно — crc32 «ветка|этап», LENSES-2 П3-2):
#   A  — согласие несёт сведения (logit a 1, c 0,3, s 1);
#   N0 — пять одинаковых вызовов при точности около 0,6 (logit a 0,3, c 1, s 0; нуль: у согласия один уровень);
#   N2 — независимые вызовы при точности около 0,6 (logit a 0,3, c 0, s 1; в первом прогоне c 0,3 — эффект у порога, LENSES-2 П3-1);
#   E  — согласие хуже вызова и на равной грубости (belief a 0,65, c 0,85, s 1,5);
#   C  — как A, потери 15 %;   D — как A, флаг контекста в rep_haiku;   Dm — как A, флаг контекста в main_opus;
#   A3 — как A, потери 3 % и по 2 задачи без записи в каждом этапе (LENSES-2 П3-3).
# Проверка контекста в сухом прогоне — из dry/ctx_<этап>.json (заглушка: флаг нет / да).
#   bash dry/dry_run.sh   (из папки опыта)
set -euo pipefail
cd "$(dirname "$0")/.."
ok_ctx () { for st in main_opus rep_opus main_haiku rep_haiku; do echo '{"flag": false, "why": [], "n": 1}' > dry/ctx_$st.json; done; }
bad_ctx () { echo '{"flag": true, "why": ["заглушка: вход выше линии"], "n": 1}' > dry/ctx_$1.json; }
run () {  # $1 — ветка; $2 a; $3 c; $4 s; $5 доля потерь; $6 режим; $7 задач без записи
  for st in main_opus rep_opus main_haiku rep_haiku; do
    smp=${st%%_*}
    python3 dry/make_stub.py $smp dry/stub_$1_$st.jsonl $2 $3 $4 $5 "$1|$st" 5 $7 $6 > /dev/null
    python3 score02.py metrics $st $smp dry/stub_$1_$st.jsonl 5 dry/evals > /dev/null
  done
  python3 analyze_score02.py --dry > dry/dry_$1.log
  cp dry/analysis_score02.json dry/analysis_$1.json
  echo "== ветка $1"; grep -E "статус" dry/dry_$1.log
}
ok_ctx
run A 1.0 0.3 1.0 0.0 logit 0
run N0 0.3 1.0 0.0 0.0 logit 0
run N2 0.3 0.0 1.0 0.0 logit 0
run E 0.65 0.85 1.5 0.0 belief 0
run C 1.0 0.3 1.0 0.15 logit 0
bad_ctx rep_haiku
run D 1.0 0.3 1.0 0.0 logit 0
ok_ctx
bad_ctx main_opus
run Dm 1.0 0.3 1.0 0.0 logit 0
ok_ctx
run A3 1.0 0.3 1.0 0.03 logit 2
python3 dry/check_expect.py expect2.json check_expect2.log
