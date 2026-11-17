#!/bin/bash
# LINUX-01, ступень Б — проба раннера: (1) тесты KUnit шести модулей в ядре (User Mode Linux), (2) готовность инструментов Rust
# для ядра (make LLVM=1 rustavailable). Только проба: переводов здесь нет. Процессор раннера, без ключей.
set -uo pipefail
OUT=$(realpath "$1")
T0=$(date +%s)
sudo apt-get update -q >/dev/null && sudo apt-get install -y -q flex bison bc libelf-dev libssl-dev clang lld llvm >/dev/null
echo "пакеты: $(( $(date +%s) - T0 )) с" | tee "$OUT/probe.log"
git clone -q --depth 1 https://github.com/torvalds/linux.git "$RUNNER_TEMP/linux" && cd "$RUNNER_TEMP/linux"
{ echo "ядро: $(git rev-parse HEAD) $(make -s kernelversion)"; echo "клон: $(( $(date +%s) - T0 )) с"; } | tee -a "$OUT/probe.log"
printf 'CONFIG_KUNIT=y\nCONFIG_INT_POW_KUNIT_TEST=y\nCONFIG_INT_SQRT_KUNIT_TEST=y\nCONFIG_GCD_KUNIT_TEST=y\nCONFIG_RATIONAL_KUNIT_TEST=y\nCONFIG_INT_LOG_KUNIT_TEST=y\nCONFIG_CMDLINE_KUNIT_TEST=y\n' > "$RUNNER_TEMP/lx.kunitconfig"
T1=$(date +%s)
python3 tools/testing/kunit/kunit.py run --kunitconfig="$RUNNER_TEMP/lx.kunitconfig" --build_dir="$RUNNER_TEMP/kbuild" --jobs=$(nproc) > "$OUT/kunit_uml.log" 2>&1
echo "KUnit в UML: код $?, $(( $(date +%s) - T1 )) с" | tee -a "$OUT/probe.log"
tail -40 "$OUT/kunit_uml.log" >> "$OUT/probe.log"
T2=$(date +%s)
command -v rustup >/dev/null || { curl -sSf https://sh.rustup.rs | sh -s -- -y; }
source "$HOME/.cargo/env" 2>/dev/null || true
RV=$(scripts/min-tool-version.sh rustc); BV=$(scripts/min-tool-version.sh bindgen)
echo "минимальные версии: rustc $RV, bindgen $BV" | tee -a "$OUT/probe.log"
rustup set profile minimal >/dev/null; rustup toolchain install "$RV" -c rust-src > "$OUT/rustup.log" 2>&1 && rustup override set "$RV" >> "$OUT/rustup.log" 2>&1
cargo install --locked bindgen-cli --version "$BV" > "$OUT/bindgen.log" 2>&1
echo "инструменты Rust: $(( $(date +%s) - T2 )) с" | tee -a "$OUT/probe.log"
make LLVM=1 rustavailable > "$OUT/rustavailable.log" 2>&1
echo "rustavailable (x86_64): код $?" | tee -a "$OUT/probe.log"
tail -5 "$OUT/rustavailable.log" >> "$OUT/probe.log"
echo "всего: $(( $(date +%s) - T0 )) с" | tee -a "$OUT/probe.log"
