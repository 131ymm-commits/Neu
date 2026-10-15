#!/bin/bash
# THINK-01: этапы одной выборки до collect_eval включительно — по образцу run_select01.sh (SELECT-01).
#   bash experiments/2026-10-15_THINK-01/run_think01.sh main   (или rep)   >> .cache/think01_live/<выборка>_run.log 2>&1
# Повторный запуск продолжает с места: драйвер не запрашивает заново вызовы с итогом, остальные шаги детерминированы.
# Правда здесь не считается: после «выборы собраны» — коммит и пуш выборов, затем truth и analyze (PREREG §9).
# Совет 34, Н7: effort драйвер задаёт на весь прогон (конфиг), поэтому задания medium и high идут ДВУМЯ процессами одновременно,
# оба по задачам в порядке сида; у high параллельность 2 (≈ 6 мин на задачу против ≈ 7 у medium), чтобы effort не смешивался со временем.
set -euo pipefail
S=${1:?нужно main или rep}
cd "$(dirname "$0")/../.."
E=experiments/2026-10-15_THINK-01
L=.cache/think01_live      # живой журнал — вне git; снимок — в $E/run/
mkdir -p $L
snap () { mkdir -p $E/run/$1 && cp -a $L/$1/. $E/run/$1/; }
STOP_AFTER=${STOP_AFTER:-6000}   # мягкая пауза запуска, с: фоновая задача живёт не дольше 2 ч
T0=$(date +%s)
left () { echo $(( STOP_AFTER - ($(date +%s) - T0) )); }
case $S in
  main) SEEDS=seeds_main.json ;;
  rep)  SEEDS=seeds_rep.json ;;
  *) echo "выборка: main или rep" >&2; exit 2 ;;
esac
unset THINK_SECRET   # соль выводится из ключа выборки (Н8); до truth она не нужна
(cd $E && python3 harness_think.py tasks $SEEDS WH && python3 harness_think.py exec_jobs ${S}_exec $SEEDS WH)
python3 tools/run_sealed2.py run --jobs $E/run/${S}_exec_jobs.jsonl --task-from-id --seed THINK-01-${S}-exec \
    --journal $L/${S}_exec_journal --streams .cache/think01_streams/${S}_exec \
    --config $E/run/think01_medium.json --parallel 3 --max-calls 75 --stop-after $(left) || { snap ${S}_exec_journal; exit 3; }
snap ${S}_exec_journal
python3 tools/run_sealed2.py export --journal $E/run/${S}_exec_journal --out $E/run/${S}_exec_out.jsonl
(cd $E && python3 harness_think.py collect_exec ${S}_exec && python3 harness_think.py eval_jobs ${S}_eval $SEEDS WH)
[ "$(left)" -gt 300 ] || { echo "пауза: до срока запуска меньше 5 минут, этап оценщиков — при продолжении"; exit 3; }
pids=(); rc=0
for eff in medium high; do
  par=$([ $eff = medium ] && echo 3 || echo 2); mc=$([ $eff = medium ] && echo 2000 || echo 260)
  python3 tools/run_sealed2.py run --jobs $E/run/${S}_eval_${eff}_jobs.jsonl --task-from-id --seed THINK-01-${S}-eval-$eff \
      --journal $L/${S}_eval_${eff}_journal --streams .cache/think01_streams/${S}_eval_$eff \
      --config $E/run/think01_$eff.json --parallel $par --max-calls $mc --stop-after $(left) >> $L/${S}_eval_$eff.log 2>&1 &
  pids+=($!)
done
for p in "${pids[@]}"; do wait $p || rc=3; done
for eff in medium high; do snap ${S}_eval_${eff}_journal; done
[ $rc = 0 ] || { echo "пауза или остановка драйвера (см. $L/${S}_eval_*.log)"; tail -1 $L/${S}_eval_medium.log; tail -1 $L/${S}_eval_high.log; exit 3; }
for eff in medium high; do python3 tools/run_sealed2.py export --journal $E/run/${S}_eval_${eff}_journal --out $E/run/${S}_eval_${eff}_out.jsonl; done
(cd $E && python3 harness_think.py collect_eval ${S}_eval)
echo "выборка $S: выборы собраны. Дальше — коммит и пуш, затем truth, analyze (PREREG §9)."
