#!/bin/bash
# PRECOND-02: этапы до collect_eval включительно — по образцу run_precond.sh PRECOND-01. Головы — в чистом контексте:
# HOME и рабочая папка вне git-дерева, CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1 (cfg_medium_clean.json; ERRORS № 118).
#   bash experiments/2026-11-02_PRECOND-02/run_precond02.sh exec pilot    — задачи и исполнитель этапа (pilot; для теста: exec A B)
#   bash experiments/2026-11-02_PRECOND-02/run_precond02.sh eval pilot    — оценщики этапа: ANCHOR и NOREF × 5 голосов
#       >> .cache/precond02_live/<этап>_run.log 2>&1
# Повторный запуск продолжает с места: драйвер не запрашивает заново вызовы с итогом. Правда здесь не считается.
set -euo pipefail
W=${1:?нужно exec или eval}; shift
cd "$(dirname "$0")/../.."
E=experiments/2026-11-02_PRECOND-02
L=.cache/precond02_live      # живой журнал — вне git; снимок — в $E/run/
mkdir -p $L
snap () { mkdir -p $E/run/$1 && cp -a $L/$1/. $E/run/$1/; }
STOP_AFTER=${STOP_AFTER:-6000}; T0=$(date +%s); left () { echo $(( STOP_AFTER - ($(date +%s) - T0) )); }
unset PRECOND02_SECRET
drive () {   # $1 — имя заданий, $2 — параллельность, $3 — предел вызовов
  python3 tools/run_sealed2.py run --jobs $E/run/$1_jobs.jsonl --task-from-id --seed PRECOND-02-$1 \
      --journal $L/$1_journal --streams .cache/precond02_streams/$1 --config $E/cfg_medium_clean.json \
      --parallel $2 --max-calls $3 --stop-after $(left)
}
case $W in
  exec)
    for st in "$@"; do
      (cd $E && python3 harness_precond02.py tasks $st && python3 harness_precond02.py exec_jobs $st)
      drive ${st}_exec 3 $(( $(wc -l < $E/run/${st}_exec_jobs.jsonl) * 3 / 2 + 2 )) >> $L/${st}_exec.log 2>&1 || { snap ${st}_exec_journal; exit 3; }
      snap ${st}_exec_journal
      python3 tools/run_sealed2.py export --journal $E/run/${st}_exec_journal --out $E/run/${st}_exec_out.jsonl
      (cd $E && python3 harness_precond02.py collect_exec $st)
    done
    echo "исполнитель: пулы этапов $* собраны" ;;
  eval)
    S=${1:?нужен этап}
    (cd $E && python3 harness_precond02.py eval_jobs $S)
    n=$(wc -l < $E/run/${S}_eval_jobs.jsonl)
    drive ${S}_eval 3 $(( n * 5 / 4 + 10 )) >> $L/${S}_eval.log 2>&1 || { snap ${S}_eval_journal; echo "пауза или остановка драйвера (см. $L/${S}_eval.log)"; exit 3; }
    snap ${S}_eval_journal
    python3 tools/run_sealed2.py export --journal $E/run/${S}_eval_journal --out $E/run/${S}_eval_out.jsonl
    (cd $E && python3 harness_precond02.py collect_eval $S)
    echo "этап $S: выборы собраны. Дальше — коммит и пуш, событие пуша, затем truth и анализ." ;;
  *) echo "режим: exec или eval" >&2; exit 2 ;;
esac
