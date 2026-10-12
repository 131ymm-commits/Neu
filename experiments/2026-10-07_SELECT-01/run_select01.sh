#!/bin/bash
# SELECT-01: этапы одной выборки до collect_eval включительно — команды PREREG §11 одной строкой.
#   bash experiments/2026-10-07_SELECT-01/run_select01.sh main   (или rep)
# Повторный запуск продолжает с места: драйвер не запрашивает заново вызовы с итогом, остальные шаги детерминированы.
# Правда здесь не считается: после этого скрипта — коммит и пуш выборов, затем truth (PREREG §11, п. 2).
# Живой журнал драйвера — .cache/select01_live/<этап>_journal; снимок в run/<этап>_journal обновляют checkin.sh и конец
# этапа, выгрузка и анализ идут по снимку (DEVIATIONS.md, 12.10). Запуск: ... run_select01.sh main >> .cache/select01_live/main_run.log 2>&1
set -euo pipefail
S=${1:?нужно main или rep}
cd "$(dirname "$0")/../.."
E=experiments/2026-10-07_SELECT-01
L=.cache/select01_live      # живой журнал — вне git (иначе хук требует коммита на каждом ходу); снимок — в $E/run/
mkdir -p $L
snap () { mkdir -p $E/run/$1 && cp -a $L/$1/. $E/run/$1/; }   # журнал только дописывается: копии достаточно
case $S in
  main) export SELECT_SECRET=/root/select_secret; SEEDS=seeds_main.json ;;
  rep)  export SELECT_SECRET=/root/select_secret_rep; SEEDS=seeds_rep.json ;;
  *) echo "выборка: main или rep" >&2; exit 2 ;;
esac
(cd $E && python3 harness.py tasks $SEEDS WH && python3 harness.py exec_jobs ${S}_exec $SEEDS WH)
python3 tools/run_sealed2.py run --jobs $E/run/${S}_exec_jobs.jsonl --task-from-id --seed SELECT-01-${S}-exec \
    --journal $L/${S}_exec_journal --streams .cache/select01_streams/${S}_exec \
    --config $E/run/select01_config.json --parallel 3 --max-calls 150
snap ${S}_exec_journal
python3 tools/run_sealed2.py export --journal $E/run/${S}_exec_journal --out $E/run/${S}_exec_out.jsonl
(cd $E && python3 harness.py collect_exec ${S}_exec && \
    python3 harness.py eval_jobs ${S}_eval B_zayavka:5,B_blind:12,C_N:5,D_N:5 $SEEDS WH)
python3 tools/run_sealed2.py run --jobs $E/run/${S}_eval_jobs.jsonl --task-from-id --seed SELECT-01-${S}-eval \
    --journal $L/${S}_eval_journal --streams .cache/select01_streams/${S}_eval \
    --config $E/run/select01_config.json --parallel 3 --max-calls 3300
snap ${S}_eval_journal
python3 tools/run_sealed2.py export --journal $E/run/${S}_eval_journal --out $E/run/${S}_eval_out.jsonl
(cd $E && python3 harness.py collect_eval ${S}_eval)
echo "выборка $S: выборы собраны. Дальше — коммит и пуш, затем truth, complete, analyze, losses (PREREG §11)."
