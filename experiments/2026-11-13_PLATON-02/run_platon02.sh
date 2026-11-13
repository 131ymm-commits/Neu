#!/bin/bash
# PLATON-02 «мимикрия»: ./run_platon02.sh pilot | build | run | analyze | audit
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"; cd "$HERE"
case "${1:-}" in
  pilot)
    python3 platon02_run.py build --seeds pilot/seeds_pilot.json --out pilot/main
    cd "$ROOT"; python3 tools/run_sealed2.py run --jobs experiments/2026-11-13_PLATON-02/pilot/main/jobs.jsonl --seed 99001 \
      --journal experiments/2026-11-13_PLATON-02/pilot/main/journal --streams /home/user/neu_heads/platon02/streams_pilot \
      --config experiments/2026-11-13_PLATON-02/cfg_platon02_haiku.json --parallel 4 --max-calls 70 ;;
  pilot2)
    python3 platon02_run.py build --seeds pilot/seeds_pilot2.json --out pilot/main2
    cd "$ROOT"; python3 tools/run_sealed2.py run --jobs experiments/2026-11-13_PLATON-02/pilot/main2/jobs.jsonl --seed 95001 \
      --journal experiments/2026-11-13_PLATON-02/pilot/main2/journal --streams /home/user/neu_heads/platon02/streams_pilot2 \
      --config experiments/2026-11-13_PLATON-02/cfg_platon02_haiku.json --parallel 4 --max-calls 70 ;;
  build)
    python3 prereg_hashes02.py --verify; python3 platon02_run.py build --seeds seeds_test.json --out run ;;
  run)
    python3 prereg_hashes02.py --verify; cd "$ROOT"
    python3 tools/run_sealed2.py run --jobs experiments/2026-11-13_PLATON-02/run/jobs.jsonl --seed 30001 \
      --journal experiments/2026-11-13_PLATON-02/run/journal --streams /home/user/neu_heads/platon02/streams_test \
      --config experiments/2026-11-13_PLATON-02/cfg_platon02_haiku.json --parallel 4 --max-calls 880 ${STOP_AFTER:+--stop-after $STOP_AFTER} ;;
  analyze)
    python3 prereg_hashes02.py --verify; python3 platon02_run.py analyze --tables run/tables.json --journal run/journal --out run/results_platon02.json ;;
  audit)
    cd "$ROOT"; python3 tools/audit_heads.py --sealed experiments/2026-11-13_PLATON-02/run/journal --out experiments/2026-11-13_PLATON-02/audit_heads_sealed.json ;;
  *) echo "использование: $0 pilot|build|run|analyze|audit"; exit 2 ;;
esac
