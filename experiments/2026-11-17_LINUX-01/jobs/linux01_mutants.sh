#!/bin/bash
# LINUX-01, пост-хок: чувствительность оценщика к мутантам переводов (harness/mutants.py). Мутантов делает скрипт механически,
# по одной правке; головы не участвуют. Тот же rustc и те же флаги, что в оценке; сравнение — 100 000 входов на функцию.
# Процессор раннера, без ключей. Повтор под именем linux01_mutants2: первый прогон упал на байте 0xA0 в выводе (ERRORS № 194).
set -euo pipefail
OUT=$(realpath "$1")
E=experiments/2026-11-17_LINUX-01
command -v rustc >/dev/null || { curl -sSf https://sh.rustup.rs | sh -s -- -y; }
source "$HOME/.cargo/env" 2>/dev/null || true
{ gcc --version | head -1; rustc --version; nproc; } | tee "$OUT/versions.txt"
cd $E && T0=$(date +%s) && python3 harness/mutants.py "$OUT/mutants.json" translations --per-file 25 --n 100000 | tee "$OUT/mutants.log"
echo "время: $(( $(date +%s) - T0 )) с" | tee -a "$OUT/mutants.log"
