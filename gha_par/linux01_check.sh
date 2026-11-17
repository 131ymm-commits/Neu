#!/bin/bash
# LINUX-01: проверка обвязки на раннере — оригиналы проходят свои тесты KUnit, оригинал против самого себя
# (100 000 входов на функцию); версии gcc и rustc. Процессор раннера, без ключей.
set -euo pipefail
OUT=$(realpath "$1")
E=experiments/2026-11-17_LINUX-01
command -v rustc >/dev/null || { curl -sSf https://sh.rustup.rs | sh -s -- -y; }
source "$HOME/.cargo/env" 2>/dev/null || true
{ gcc --version | head -1; rustc --version; } | tee "$OUT/versions.txt"
cd $E && python3 harness/run.py check "$OUT/check.json" --n 100000 | tee "$OUT/check.log"
