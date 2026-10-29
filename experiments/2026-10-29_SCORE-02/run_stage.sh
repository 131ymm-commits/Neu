#!/bin/bash
# SCORE-02: запуск (и продолжение той же командой) одного этапа теста — ровно команда PREREG §7. Из корня репозитория:
#   bash experiments/2026-10-29_SCORE-02/run_stage.sh <main_opus|rep_opus|main_haiku|rep_haiku>
# Выход с кодом 3 — мягкая пауза по --stop-after (начатые вызовы дописаны); продолжение — тот же вызов.
set -euo pipefail
cd "$(dirname "$0")/../.."
E=experiments/2026-10-29_SCORE-02
case "$1" in
  main_opus)  J=main; S=211; C=opus ;;
  rep_opus)   J=rep;  S=212; C=opus ;;
  main_haiku) J=main; S=213; C=haiku ;;
  rep_haiku)  J=rep;  S=214; C=haiku ;;
  *) echo "неизвестный этап: $1" >&2; exit 2 ;;
esac
exec python3 tools/run_sealed2.py run --jobs $E/jobs/${J}_jobs.jsonl --seed $S --journal $E/run/$1 --streams .cache/score02_streams/$1 \
  --config $E/jobs/cfg_${C}_clean.json --parallel 4 --stop-after 6600
