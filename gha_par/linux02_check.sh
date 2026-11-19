#!/bin/bash
# LINUX-02: официальная проверка обвязки на раннере (PLAN-PILOT.md: «Проверка обвязки до переводов — на GitHub Actions»):
# оригиналы шести модулей проходят свои тесты KUnit, оригинал против себя — 0 расхождений (20 000 обычных и 20 000 крайних
# проверок на функцию), то же под UBSan (по 2 000); версии gcc и rustc. Переводы не трогаются. Процессор раннера, без ключей.
set -uo pipefail
OUT=$(realpath "$1")
E=experiments/2026-11-19_LINUX-02
command -v rustc >/dev/null || { curl -sSf https://sh.rustup.rs | sh -s -- -y; }
source "$HOME/.cargo/env" 2>/dev/null || true
{ gcc --version | head -1; rustc --version; nproc; git rev-parse HEAD; } | tee "$OUT/versions.txt"
cd $E || exit 1
T0=$(date +%s)
python3 harness/run.py check "$OUT/check.json" | tee "$OUT/check.log"
echo "время: $(( $(date +%s) - T0 )) с" | tee -a "$OUT/check.log"
