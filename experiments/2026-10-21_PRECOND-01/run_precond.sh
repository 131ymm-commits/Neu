#!/bin/bash
# PRECOND-01: этапы основного опыта до collect_eval включительно — по образцу run_think01.sh (THINK-01).
#   bash experiments/2026-10-21_PRECOND-01/run_precond.sh exec   — задачи и исполнитель обоих этапов (open: 9, val: 50 задач)
#   bash experiments/2026-10-21_PRECOND-01/run_precond.sh open   — оценщики открытия: medium (585) и high (18) двумя процессами
#   bash experiments/2026-10-21_PRECOND-01/run_precond.sh val    — оценщики проверки победителя: medium (до 750) по winners.json
#       >> .cache/precond01_live/<этап>_run.log 2>&1
# Повторный запуск продолжает с места: драйвер не запрашивает заново вызовы с итогом. Правда здесь не считается (PREREG §9).
set -euo pipefail
S=${1:?нужно exec, open или val}
cd "$(dirname "$0")/../.."
E=experiments/2026-10-21_PRECOND-01
L=.cache/precond01_live      # живой журнал — вне git; снимок — в $E/run/
mkdir -p $L
snap () { mkdir -p $E/run/$1 && cp -a $L/$1/. $E/run/$1/; }
STOP_AFTER=${STOP_AFTER:-6000}; T0=$(date +%s); left () { echo $(( STOP_AFTER - ($(date +%s) - T0) )); }
unset PRECOND_SECRET
drive () {   # $1 — имя заданий, $2 — effort, $3 — параллельность, $4 — предел вызовов
  python3 tools/run_sealed2.py run --jobs $E/run/$1_jobs.jsonl --task-from-id --seed PRECOND-01-$1 \
      --journal $L/$1_journal --streams .cache/precond01_streams/$1 --config $E/run/precond_$2.json \
      --parallel $3 --max-calls $4 --stop-after $(left)
}
case $S in
  exec)
    for st in open val; do
      (cd $E && python3 harness_precond.py tasks $st && python3 harness_precond.py exec_jobs $st)
      drive ${st}_exec medium 3 $(( $(wc -l < $E/run/${st}_exec_jobs.jsonl) * 3 / 2 )) >> $L/${st}_exec.log 2>&1 || { snap ${st}_exec_journal; exit 3; }
      snap ${st}_exec_journal
      python3 tools/run_sealed2.py export --journal $E/run/${st}_exec_journal --out $E/run/${st}_exec_out.jsonl
      (cd $E && python3 harness_precond.py collect_exec $st)
    done
    echo "исполнитель: пулы обоих этапов собраны" ;;
  open|val)
    [ $S = val ] && [ ! -f $E/winners.json ] && { echo "нет winners.json — сначала анализ открытия"; exit 2; }
    (cd $E && python3 harness_precond.py eval_jobs $S)
    pids=(); rc=0
    for eff in medium high; do
      [ -f $E/run/${S}_eval_${eff}_jobs.jsonl ] || continue
      n=$(wc -l < $E/run/${S}_eval_${eff}_jobs.jsonl)
      drive ${S}_eval_${eff} $eff $([ $eff = medium ] && echo 3 || echo 2) $(( n * 5 / 4 + 10 )) >> $L/${S}_eval_$eff.log 2>&1 &
      pids+=($!)
    done
    for p in "${pids[@]}"; do wait $p || rc=3; done
    for eff in medium high; do [ -d $L/${S}_eval_${eff}_journal ] && snap ${S}_eval_${eff}_journal; done
    [ $rc = 0 ] || { echo "пауза или остановка драйвера (см. $L/${S}_eval_*.log)"; exit 3; }
    for eff in medium high; do
      [ -d $E/run/${S}_eval_${eff}_journal ] && python3 tools/run_sealed2.py export --journal $E/run/${S}_eval_${eff}_journal --out $E/run/${S}_eval_${eff}_out.jsonl
    done
    (cd $E && python3 harness_precond.py collect_eval $S)
    echo "этап $S: выборы собраны. Дальше — коммит и пуш, событие пуша, затем truth и analyze (PREREG §9)." ;;
  *) echo "этап: exec, open или val" >&2; exit 2 ;;
esac
