#!/bin/bash
# PLAY-01: шаг этапа после завершения всех workflow раунда: принять решения голов и сыграть раунд.
#   bash step.sh <этап> <раунд>   (ид задач workflow — runs/<этап>/r<раунд>/tasks.txt)
set -e
cd "$(dirname "$0")"
T=/tmp/claude-0/-home-user-Neu/5dc61be6-6c38-58c2-939b-4b416832b0f1/tasks
files=""
for id in $(cat runs/$1/r$2/tasks.txt); do
  f=$T/$id.output
  python3 -c "import json,sys; d=json.load(open('$f')); assert d.get('result'), 'нет результата'" || { echo "не готов: $id"; exit 3; }
  files="$files $f"
done
python3 tourney.py ingest $1 $files
python3 tourney.py play $1
python3 tourney.py status $1
