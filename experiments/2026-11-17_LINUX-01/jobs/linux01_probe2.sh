#!/bin/bash
# LINUX-01, ступень Б — проба 2: тесты KUnit пяти модулей в ядре (User Mode Linux). Проба 1 не собрала конфигурацию:
# RATIONAL_KUNIT_TEST зависит от RATIONAL, а RATIONAL — скрытый символ (tristate без подсказки, lib/math/Kconfig), его
# включает только select другого драйвера; в kunitconfig его задать нельзя (ERRORS № 192). Здесь rational исключён.
# Только проба: переводов здесь нет. Процессор раннера, без ключей.
set -uo pipefail
OUT=$(realpath "$1")
T0=$(date +%s)
sudo apt-get update -q >/dev/null && sudo apt-get install -y -q flex bison bc libelf-dev libssl-dev >/dev/null
echo "пакеты: $(( $(date +%s) - T0 )) с" | tee "$OUT/probe.log"
git clone -q --depth 1 https://github.com/torvalds/linux.git "$RUNNER_TEMP/linux" && cd "$RUNNER_TEMP/linux"
{ echo "ядро: $(git rev-parse HEAD) $(make -s kernelversion)"; echo "клон: $(( $(date +%s) - T0 )) с"; } | tee -a "$OUT/probe.log"
printf 'CONFIG_KUNIT=y\nCONFIG_INT_POW_KUNIT_TEST=y\nCONFIG_INT_SQRT_KUNIT_TEST=y\nCONFIG_GCD_KUNIT_TEST=y\nCONFIG_INT_LOG_KUNIT_TEST=y\nCONFIG_CMDLINE_KUNIT_TEST=y\n' > "$RUNNER_TEMP/lx.kunitconfig"
cp "$RUNNER_TEMP/lx.kunitconfig" "$OUT/kunitconfig.txt"
T1=$(date +%s)
python3 tools/testing/kunit/kunit.py run --kunitconfig="$RUNNER_TEMP/lx.kunitconfig" --build_dir="$RUNNER_TEMP/kbuild" --jobs=$(nproc) > "$OUT/kunit_uml.log" 2>&1
echo "KUnit в UML: код $?, $(( $(date +%s) - T1 )) с" | tee -a "$OUT/probe.log"
grep -E "^\[[0-9:]+\] (=+ |Testing complete|Elapsed time|ERROR)|Ran [0-9]+ tests" "$OUT/kunit_uml.log" | tail -40 >> "$OUT/probe.log"
echo "всего: $(( $(date +%s) - T0 )) с" | tee -a "$OUT/probe.log"
