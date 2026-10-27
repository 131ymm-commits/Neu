#!/bin/bash
# PRECOND-01, пилот на high: 20 вызовов оценщика (Opus, effort high) тем же драйвером и CLI (pilot_high.py — клетки и правило).
#   bash experiments/2026-10-21_PRECOND-01/run_pilot_high.sh      (из корня репозитория; продолжает с места после паузы)
set -uo pipefail
cd "$(dirname "$0")/../.."
E=experiments/2026-10-21_PRECOND-01; L=.cache/precond01_live; mkdir -p $L $E/run
(cd $E && python3 pilot_high.py jobs) || exit 2
python3 tools/run_sealed2.py run --jobs $E/run/pilot_high_jobs.jsonl --task-from-id --seed PRECOND-01-pilot-high \
    --journal $L/pilot_high_journal --streams .cache/precond01_streams/pilot_high \
    --config $E/run/precond_high.json --parallel 2 --max-calls 30 --stop-after 6000 >> $L/pilot_high.log 2>&1
rc=$?; mkdir -p $E/run/pilot_high_journal && cp -a $L/pilot_high_journal/. $E/run/pilot_high_journal/
[ $rc = 0 ] || { echo "пауза или остановка драйвера (см. $L/pilot_high.log)"; tail -1 $L/pilot_high.log; exit 3; }
python3 tools/run_sealed2.py export --journal $E/run/pilot_high_journal --out $E/run/pilot_high_out.jsonl
(cd $E && PRECOND_TAG=pilot_high python3 pilot_high.py collect && python3 pilot_high.py analyze)
echo "пилот PRECOND-01 на high: выборы собраны и разобраны"
