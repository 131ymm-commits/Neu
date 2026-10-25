#!/bin/bash
# PRECOND-01, пилот: 96 вызовов оценщика (Opus, effort medium) тем же драйвером и CLI, что SELECT-01 и THINK-01.
#   bash experiments/2026-10-21_PRECOND-01/run_pilot.sh      (из корня репозитория; продолжает с места после паузы)
set -uo pipefail
cd "$(dirname "$0")/../.."
E=experiments/2026-10-21_PRECOND-01; L=.cache/precond01_live; mkdir -p $L $E/run
# PRECOND_WITH_THINK=1 — параллельно с повтором THINK-01, по слову автора 25.10: «запускай недоделанные прогоны» (DECISIONS 25.10)
if [ "${PRECOND_WITH_THINK:-0}" != 1 ] && pgrep -f "^bash experiments/2026-10-15_THINK-01/run_think01.sh" > /dev/null; then
  echo "идёт прогон THINK-01 — пилот не запускаю: пока идёт выборка, других голов не запускать"; exit 4
fi
(cd $E && python3 pilot_precond.py jobs) || exit 2
python3 tools/run_sealed2.py run --jobs $E/run/pilot_jobs.jsonl --task-from-id --seed PRECOND-01-pilot \
    --journal $L/pilot_journal --streams .cache/precond01_streams/pilot \
    --config $E/run/precond_medium.json --parallel 3 --max-calls 110 --stop-after 6000 >> $L/pilot.log 2>&1
rc=$?; mkdir -p $E/run/pilot_journal && cp -a $L/pilot_journal/. $E/run/pilot_journal/
[ $rc = 0 ] || { echo "пауза или остановка драйвера (см. $L/pilot.log)"; tail -1 $L/pilot.log; exit 3; }
python3 tools/run_sealed2.py export --journal $E/run/pilot_journal --out $E/run/pilot_out.jsonl
(cd $E && python3 pilot_precond.py collect && python3 pilot_precond.py analyze)
echo "пилот PRECOND-01: выборы собраны и разобраны"
