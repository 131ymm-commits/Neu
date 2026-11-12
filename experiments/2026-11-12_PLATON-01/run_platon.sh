#!/bin/bash
# PLATON-01: тест после регистрации. Шаги:
#   ./run_platon.sh build    — сверка хешей, задания теста run/jobs.jsonl (+ tables.json, prompts.sha256)
#   ./run_platon.sh run      — головы через tools/run_sealed2.py (продолжение с места той же командой)
#   ./run_platon.sh analyze  — сверка хешей, анализ → run/results_platon01.json
#   ./run_platon.sh audit    — аудит входа голов (tools/audit_heads.py --sealed) → audit_heads_sealed.json
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
cd "$HERE"
case "${1:-}" in
  build)
    python3 prereg_hashes.py --verify
    python3 platon_jobs.py build --seeds seeds_test.json --heads 4 --out run
    ;;
  run)
    python3 prereg_hashes.py --verify
    cd "$ROOT"
    python3 tools/run_sealed2.py run --jobs experiments/2026-11-12_PLATON-01/run/jobs.jsonl --seed 10001 \
      --journal experiments/2026-11-12_PLATON-01/run/journal --streams /home/user/neu_heads/platon01/streams_test \
      --config experiments/2026-11-12_PLATON-01/cfg_platon_haiku.json --parallel 4 --max-calls 700 ${STOP_AFTER:+--stop-after $STOP_AFTER}
    ;;
  analyze)
    python3 prereg_hashes.py --verify
    python3 platon_analyze.py --tables run/tables.json --journal run/journal --out run/results_platon01.json
    ;;
  audit)
    cd "$ROOT"
    python3 tools/audit_heads.py --sealed experiments/2026-11-12_PLATON-01/run/journal --out experiments/2026-11-12_PLATON-01/audit_heads_sealed.json
    ;;
  *)
    echo "использование: $0 build|run|analyze|audit"; exit 2 ;;
esac
