#!/bin/bash
# PLATON-01R: повтор PLATON-01 на claude-sonnet-5-5. Код мира, разбора и анализа — из ../2026-11-12_PLATON-01 без изменений
# (sha256 сверяются с его prereg_hashes.json и с prereg_hashes_r.json).
#   ./run_platon_r.sh pilot | build | run | analyze | audit
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
P1="$HERE/../2026-11-12_PLATON-01"
cd "$HERE"
case "${1:-}" in
  pilot)
    python3 "$P1/platon_jobs.py" build --seeds pilot/seeds_pilot_r.json --heads 4 --out pilot/main --variant b --regimes free,forced
    cd "$ROOT"
    python3 tools/run_sealed2.py run --jobs experiments/2026-11-13_PLATON-01R/pilot/main/jobs.jsonl --seed 90040 \
      --journal experiments/2026-11-13_PLATON-01R/pilot/main/journal --streams /home/user/neu_heads/platon01r/streams_pilot \
      --config experiments/2026-11-13_PLATON-01R/cfg_platon_sonnet.json --parallel 4 --max-calls 70
    ;;
  build)
    python3 prereg_hashes_r.py --verify
    python3 "$P1/platon_jobs.py" build --seeds seeds_test_r.json --heads 4 --out run --variant b --regimes free,forced
    ;;
  run)
    python3 prereg_hashes_r.py --verify
    cd "$ROOT"
    python3 tools/run_sealed2.py run --jobs experiments/2026-11-13_PLATON-01R/run/jobs.jsonl --seed 20001 \
      --journal experiments/2026-11-13_PLATON-01R/run/journal --streams /home/user/neu_heads/platon01r/streams_test \
      --config experiments/2026-11-13_PLATON-01R/cfg_platon_sonnet.json --parallel 4 --max-calls 1300
    ;;
  analyze)
    python3 prereg_hashes_r.py --verify
    python3 "$P1/platon_analyze.py" --tables run/tables.json --journal run/journal --out run/results_platon01r.json
    python3 "$P1/platon_analyze.py" --tables run/tables.json --journal run/journal --out run/results_platon01r_tau005.json --tau 0.05
    python3 "$P1/platon_analyze.py" --tables run/tables.json --journal run/journal --out run/results_platon01r_tau02.json --tau 0.2
    ;;
  audit)
    cd "$ROOT"
    python3 tools/audit_heads.py --sealed experiments/2026-11-13_PLATON-01R/run/journal --out experiments/2026-11-13_PLATON-01R/audit_heads_sealed.json
    ;;
  *) echo "использование: $0 pilot|build|run|analyze|audit"; exit 2 ;;
esac
