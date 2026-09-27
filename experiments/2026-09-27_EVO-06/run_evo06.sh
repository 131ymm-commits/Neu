#!/bin/bash
# EVO-06: очередь с продолжением с места остановки (та же схема resume, что в experiments/run_queue.sh:
# строки jobs.txt «задача ветвь сид», готовые runs/*.json пропускаются). Общая очередь run_queue.sh не трогается —
# она относится к EVO-03/04/05; этот скрипт ждёт, пока она опустеет, и только потом занимает ядра.
# Использование:  ./run_evo06.sh            — основной прогон (jobs.txt → runs/), 2 процесса, OMP_NUM_THREADS=1
#                 ./run_evo06.sh pilot      — пилот (pilot/jobs.txt → pilot/, EVO06_GENS=60, сиды 996–997, в тест не входят)
#                 анализ пилота: EVO06_GENS=60 python3 evo06_analyze.py pilot pilot/pilot_results.json (анализ сверяет gens и хеш кода)
#                 P=4 ./run_evo06.sh        — число процессов
set -u
cd "$(dirname "$0")"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
P=${P:-2}
if [ "${1:-}" = "pilot" ]; then
  OUT=pilot; JOBS=pilot/jobs.txt; export EVO06_GENS=${EVO06_GENS:-60}
else
  OUT=runs; JOBS=jobs.txt; unset EVO06_GENS        # основной прогон всегда 150 поколений, даже если EVO06_GENS остался в окружении
  # ждём общую очередь: шаблон совпадает только с самим запуском «bash …/run_queue.sh», а не с оболочкой, в чьей командной
  # строке это имя лишь упомянуто (`pgrep -f run_queue.sh` совпал бы с ней и ждал бы вечно — REVIEW_gate2 2.8; проверено)
  while pgrep -f 'bash .*run_queue\.sh$' > /dev/null || pgrep -f 'bash .*run_evo05\.sh$' > /dev/null; do sleep 60; done
fi
mkdir -p "$OUT"; export EVO06_OUT="$OUT"
{ echo "== $(date '+%F %T') старт EVO-06 ($OUT), P=$P, GENS=${EVO06_GENS:-150}"; python3 -c "import sys,numpy;print('python',sys.version.split()[0],'numpy',numpy.__version__)";
  python3 -c "import evo06;print('код',evo06.code_hash())"; } >> "$OUT/run.log"
# строка jobs: «задача ветвь сид [турнир]»; имя файла — как в evo06.py
while read t a s tour; do
  n="${t}_${a}_s${s}"; [ -n "${tour:-}" ] && [ "$tour" != 5 ] && n="${n}_tour${tour}"
  [ -f "$OUT/$n.json" ] || echo "$t $a $s${tour:+ $tour}"     # без хвостового пробела: xargs -L склеил бы строки
done < "$JOBS" | xargs -r -P "$P" -L 1 nice -n 5 python3 evo06.py >> "$OUT/run.log" 2>&1
echo "== $(date '+%F %T') EVO-06 ($OUT) готово: $(ls "$OUT"/*.json 2>/dev/null | wc -l) файлов" >> "$OUT/run.log"
tail -3 "$OUT/run.log"
