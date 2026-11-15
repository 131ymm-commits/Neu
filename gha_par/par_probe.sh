#!/bin/bash
# Проверка параллельного workflow neu-par: машина и время начала и конца (сравнить с api_probe — шли ли они одновременно).
set -euo pipefail
OUT="$1"
{ echo "начало: $(date -u +%H:%M:%S)"; echo "ядер: $(nproc)"; echo "раннер: ${RUNNER_NAME:-?}"; sleep 60; echo "конец: $(date -u +%H:%M:%S)"; } | tee "$OUT/probe.txt"
