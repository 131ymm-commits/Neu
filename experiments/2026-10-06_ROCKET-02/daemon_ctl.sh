#!/bin/bash
# Управление миром ROCKET-02 (слот 6): ./daemon_ctl.sh attach | restore | fresh
#   attach  — поднять демон к живому серверу без сброса (после checkpoint или падения демона)
#   restore — после перезапуска контейнера: сервер из последнего сохранения + attach
#   fresh   — новый мир (сброс FLE)
cd "$(dirname "$0")"; B=/tmp/claude-0/fact; D=$B/slot6; SAVE=$D/saves/rocket2_ckpt.zip
waitready() { for i in $(seq 60); do grep -q "READY\|Traceback" $B/rocket2.log && break; sleep 3; done; grep -v "Loading action" $B/rocket2.log | grep "READY\|Traceback\|восстановление"; }
case "$1" in
attach) (NEU_ATTACH=1 nohup /tmp/claude-0/flevenv/bin/python campaign_daemon.py 6 $PWD/campaign > $B/rocket2.log 2>&1 &); waitready ;;
restore)
  for P in $(ps -eo pid,args | awk '/campaign_daemon.py 6|slot6\/bin\/x64\/factorio/ && !/awk/ {print $1}'); do kill $P; done; sleep 3; rm -f $D/.lock
  (tail -f /dev/null | $D/bin/x64/factorio --start-server $SAVE --port 34203 --rcon-port 27106 --rcon-password factorio --server-settings $B/server-settings.json > $B/slot6.log 2>&1 &)
  for i in $(seq 30); do grep -q "Starting RCON" $B/slot6.log && break; sleep 2; done
  (NEU_ATTACH=1 nohup /tmp/claude-0/flevenv/bin/python campaign_daemon.py 6 $PWD/campaign > $B/rocket2.log 2>&1 &); waitready ;;
fresh) (nohup /tmp/claude-0/flevenv/bin/python campaign_daemon.py 6 $PWD/campaign > $B/rocket2.log 2>&1 &); waitready ;;
esac
