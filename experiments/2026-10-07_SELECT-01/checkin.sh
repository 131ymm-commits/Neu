#!/bin/bash
# SELECT-01: проверка прогона по расписанию (PREREG §10) — короткая сводка, затем коммит и пуш журналов выборки.
#   bash experiments/2026-10-07_SELECT-01/checkin.sh main   (или rep)
set -uo pipefail
S=${1:?нужно main или rep}
cd "$(dirname "$0")/../.."
E=experiments/2026-10-07_SELECT-01
L=.cache/select01_live
if pgrep -f "^bash experiments/2026-10-07_SELECT-01/run_select01.sh $S" > /dev/null; then echo "процесс: идёт"; else echo "процесс: НЕ идёт"; fi
for j in ${S}_exec_journal ${S}_eval_journal; do       # снимок живого журнала в run/ (журнал только дописывается)
  [ -d $L/$j ] && mkdir -p $E/run/$j && cp -a $L/$j/. $E/run/$j/
done
[ -f $L/${S}_run.log ] && cp -a $L/${S}_run.log $E/run/${S}_run.log
python3 - "$E" "$S" <<'EOF'
import json, sys, os, glob
E, S = sys.argv[1], sys.argv[2]
for stage in ('exec', 'eval'):
    j = f'{E}/run/{S}_{stage}_journal'
    if not os.path.isdir(j):
        continue
    fin = na = lost = 0
    for p in glob.glob(j + '/*.jsonl'):
        if p.endswith('run_log.jsonl'):
            continue
        for line in open(p, encoding='utf-8'):
            r = json.loads(line)
            fin += bool(r.get('final')); lost += r.get('final') == 'потерян'; na += r['outcome'] == 'нет ответа'
    jobs = sum(1 for _ in open(f'{E}/run/{S}_{stage}_jobs.jsonl')) if os.path.exists(f'{E}/run/{S}_{stage}_jobs.jsonl') else '?'
    log = [json.loads(x) for x in open(j + '/run_log.jsonl', encoding='utf-8') if x.strip()] if os.path.exists(j + '/run_log.jsonl') else []
    stops = [e for e in log if e.get('event') in ('стоп', 'ошибка')]
    calls = sum(1 for e in log if e.get('event') == 'вызов')
    print(f'{stage}: итогов {fin} из {jobs}, потеряно {lost}, попыток «нет ответа» {na}, вызовов начато {calls}',
          ('| последняя остановка: ' + stops[-1]['at'] + ' ' + stops[-1].get('reason', '')[:160]) if stops else '')
EOF
tail -n 2 $E/run/${S}_run.log | cut -c1-200
for f in $E/run/${S}_exec_jobs.jsonl $E/run/${S}_exec_journal $E/run/${S}_eval_journal $E/run/${S}_run.log \
         $E/run/${S}_exec_out.jsonl $E/run/${S}_eval_out.jsonl $E/run/${S}_exec_pools.sha256 $E/tasks $E/pools $E/evals; do
  [ -e "$f" ] && git add "$f"          # несуществующий путь не должен срывать весь git add
done
if ! git diff --cached --quiet; then
  git -c user.name=Claude -c user.email=noreply@anthropic.com commit -q -m "SELECT-01 $S: журнал прогона (контрольная точка $(date -u +%d.%m\ %H:%M) UTC)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EAUcgUVu3BhYQ16NUm8BDT" && git push -q origin HEAD:main 2>&1 | tail -1 && echo "коммит: $(git log --oneline -1 | cut -c1-9)"
else
  echo "коммит: изменений нет"
fi
