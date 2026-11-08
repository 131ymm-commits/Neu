#!/bin/bash
# PRECOND-02: проверка прогона по расписанию — короткая сводка, снимок живых журналов в run/, коммит и пуш (по образцу checkin_precond.sh PRECOND-01).
#   bash experiments/2026-11-02_PRECOND-02/checkin_precond02.sh <этап>   (exec — пока идёт исполнитель A и B; A или B — оценщики)
# В хеши регистрации не входит: на задания, выборы, правду и анализ не влияет (урок ERRORS № 93).
set -uo pipefail
S=${1:?нужно exec, A или B}
cd "$(dirname "$0")/../.."
E=experiments/2026-11-02_PRECOND-02
L=.cache/precond02_live
if pgrep -f "^bash experiments/2026-11-02_PRECOND-02/run_precond02.sh" > /dev/null; then echo "процесс: идёт"; else echo "процесс: НЕ идёт"; fi
for j in A_exec_journal B_exec_journal ${S}_eval_journal; do
  [ -d $L/$j ] && mkdir -p $E/run/$j && cp -a $L/$j/. $E/run/$j/
done
for f in $L/${S}_run.log $L/exec_run.log; do [ -f $f ] && cp -a $f $E/run/; done
python3 - "$E" <<'PY'
import json, sys, os, glob
E = sys.argv[1]
for j in ('A_exec', 'B_exec', 'A_eval', 'B_eval'):
    d = f'{E}/run/{j}_journal'
    if not os.path.isdir(d): continue
    fin = lost = na = 0
    for p in glob.glob(d + '/WH_*.jsonl'):
        for line in open(p, encoding='utf-8'):
            r = json.loads(line); fin += bool(r.get('final')); lost += r.get('final') == 'потерян'; na += r['outcome'] == 'нет ответа'
    jf = f'{E}/run/{j}_jobs.jsonl'; n = sum(1 for _ in open(jf)) if os.path.exists(jf) else '?'
    print(f'{j}: итогов {fin} из {n}, потеряно {lost}, попыток «нет ответа» {na}')
PY
for f in $E/run/A_exec_journal $E/run/B_exec_journal $E/run/${S}_eval_journal $E/run/${S}_run.log $E/run/exec_run.log; do
  [ -e "$f" ] && git add "$f"
done
if ! git diff --cached --quiet; then
  git -c user.name=Claude -c user.email=noreply@anthropic.com commit -q -m "PRECOND-02 $S: журнал прогона (контрольная точка $(date -u +%d.%m\ %H:%M) UTC)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EAUcgUVu3BhYQ16NUm8BDT" && git push -q origin HEAD:main 2>&1 | tail -1 && echo "коммит: $(git log --oneline -1 | cut -c1-9)"
else
  echo "коммит: изменений нет"
fi
