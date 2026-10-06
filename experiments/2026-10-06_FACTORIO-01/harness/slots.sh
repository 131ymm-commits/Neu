#!/bin/bash
# Слоты: независимые серверы Factorio 2.0.77 (headless) со сценарием FLE default_lab_scenario. ./slots.sh start N | stop
BASE=/tmp/claude-0/fact; SRC=$BASE/factorio
case "$1" in
start)
  for k in $(seq 0 $(($2-1))); do
    D=$BASE/slot$k; [ -d $D ] || cp -r $SRC $D; rm -f $D/.lock
    (tail -f /dev/null | $D/bin/x64/factorio --start-server-load-scenario default_lab_scenario --port $((34197+k)) --rcon-port $((27100+k)) --rcon-password factorio \
       --server-settings $BASE/server-settings.json --map-gen-settings $BASE/map-gen-settings.json --map-settings $BASE/map-settings.json > $BASE/slot$k.log 2>&1 &)
  done ;;
stop) for p in $(pgrep -x factorio); do kill -9 $p; done ;;
esac
