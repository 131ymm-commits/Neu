#!/bin/bash
# ЯДРО-UML, проба 2 (experiments/2026-11-19_KERNEL-UML/PLAN.md). Проба 1: у UML есть select HAVE_RUST, но CONFIG_RUST не
# включился ни под um, ни под x86_64 («Missing: CONFIG_RUST=y»). Предположение (не проверено): rustup override стоял для папки
# исходников, а kunit.py собирает в O=папке — там другой toolchain без rust-src. Здесь: toolchain по умолчанию с rust-src,
# rustavailable с O=, выписка зависимостей RUST из .config. Дальше — как в пробе 1: собирается ли ядро с CONFIG_RUST под ARCH=um и
# идёт ли KUnit int_pow, если int_pow заменён переводом на Rust из LINUX-01 (три головы, все верны в ступени А).
# Запасной путь — --arch=x86_64 (QEMU). Только проба: головы не вызываются, ключей нет. Процессор раннера.
set -uo pipefail
OUT=$(realpath "$1")
NEU=$PWD
T0=$(date +%s)
sudo apt-get update -q >/dev/null && sudo apt-get install -y -q flex bison bc libelf-dev libssl-dev clang lld llvm qemu-system-x86 >/dev/null
echo "пакеты: $(( $(date +%s) - T0 )) с" | tee "$OUT/probe.log"
git clone -q --depth 1 --branch v7.4-rc3 https://github.com/torvalds/linux.git "$RUNNER_TEMP/linux" && cd "$RUNNER_TEMP/linux" || exit 1
{ echo "ядро: $(git rev-parse HEAD) $(make -s kernelversion)"; echo "клон: $(( $(date +%s) - T0 )) с"; } | tee -a "$OUT/probe.log"
command -v rustup >/dev/null || { curl -sSf https://sh.rustup.rs | sh -s -- -y; }
source "$HOME/.cargo/env" 2>/dev/null || true
RV=$(scripts/min-tool-version.sh rustc); BV=$(scripts/min-tool-version.sh bindgen)
echo "минимальные версии: rustc $RV, bindgen $BV" | tee -a "$OUT/probe.log"
rustup set profile minimal >/dev/null; rustup toolchain install "$RV" -c rust-src > "$OUT/rustup.log" 2>&1 && rustup default "$RV" >> "$OUT/rustup.log" 2>&1
cargo install --locked bindgen-cli --version "$BV" > "$OUT/bindgen.log" 2>&1
{ rustc --version; bindgen --version; clang --version | head -1; echo "инструменты: $(( $(date +%s) - T0 )) с"; } | tee -a "$OUT/probe.log"
{ echo "--- HAVE_RUST в Kconfig архитектур:"; grep -n "HAVE_RUST" arch/um/Kconfig arch/x86/Kconfig arch/Kconfig init/Kconfig 2>/dev/null | head -20; } | tee -a "$OUT/probe.log"
{ echo "--- зависимости config RUST (init/Kconfig):"; awk '/^config RUST$/{f=1} f&&/^config /&&!/^config RUST$/{exit} f' init/Kconfig; } | tee -a "$OUT/probe.log"
for a in um x86_64; do
  mkdir -p "$RUNNER_TEMP/kbuild_$a"
  { echo "--- rustc в папке сборки $a: $(cd "$RUNNER_TEMP/kbuild_$a" && rustc --version)"; \
    make ARCH=$a LLVM=1 O="$RUNNER_TEMP/kbuild_$a" rustavailable 2>&1 | tail -6 | sed "s/^/  rustavailable $a: /"; } | tee -a "$OUT/probe.log"
done
printf 'CONFIG_KUNIT=y\nCONFIG_INT_POW_KUNIT_TEST=y\nCONFIG_RUST=y\n' > "$RUNNER_TEMP/lx.kunitconfig"
cp "$RUNNER_TEMP/lx.kunitconfig" "$OUT/kunitconfig.txt"
kunit_run () {   # $1 — архитектура, $2 — имя журнала
  local T1=$(date +%s) a="$1" log="$OUT/$2.log" bd="$RUNNER_TEMP/kbuild_$1"
  python3 tools/testing/kunit/kunit.py run --arch="$a" --make_options LLVM=1 --kunitconfig="$RUNNER_TEMP/lx.kunitconfig" \
    --build_dir="$bd" --jobs=$(nproc) --timeout=600 > "$log" 2>&1
  local rc=$?
  echo "$2 ($a): код $rc, $(( $(date +%s) - T1 )) с; CONFIG_RUST в .config: $(grep -c '^CONFIG_RUST=y' "$bd/.config" 2>/dev/null)" | tee -a "$OUT/probe.log"
  grep -E "^(# )?CONFIG_(RUST|RUST_IS_AVAILABLE|MODVERSIONS|GENDWARFKSYMS|RANDSTRUCT[A-Z_]*|DEBUG_INFO_BTF|CFI[A-Z_]*|CC_IS_CLANG|LTO[A-Z_]*|KASAN[A-Z_]*)[ =]" "$bd/.config" 2>/dev/null \
    | head -20 | sed "s/^/  .config: /" | tee -a "$OUT/probe.log"
  grep -E "Ran [0-9]+ tests|passed|failed|ERROR|error\[|error:|Not all Kconfig|missing" "$log" | tail -12 | tee -a "$OUT/probe.log"
  return $rc
}
# А. контроль: оригинал на C, Rust включён
ARCH_OK=um
kunit_run um control_um || { echo "UML с Rust не вышло — запасной путь x86_64 (QEMU)" | tee -a "$OUT/probe.log"; ARCH_OK=x86_64; kunit_run x86_64 control_x86_64; }
# Б. подмена int_pow переводом из LINUX-01
{ echo "--- lib/math/Makefile до подмены:"; grep -n "int_pow" lib/math/Makefile; } | tee -a "$OUT/probe.log"
sed -i 's/\bint_pow\.o\b/int_pow_rs.o/' lib/math/Makefile
if [ "$(grep -c 'int_pow_rs\.o' lib/math/Makefile)" -lt 1 ]; then echo "ПОДМЕНА НЕ УДАЛАСЬ: в Makefile нет int_pow.o" | tee -a "$OUT/probe.log"; exit 1; fi
grep -n "int_pow" lib/math/Makefile | tee -a "$OUT/probe.log"
BD="$RUNNER_TEMP/kbuild_$ARCH_OK"
for h in haiku sonnet opus; do
  cp "$NEU/experiments/2026-11-17_LINUX-01/translations/$h/int_pow.rs" lib/math/int_pow_rs.rs
  rm -f "$BD/lib/math/int_pow_rs.o"
  kunit_run "$ARCH_OK" "trans_${h}_$ARCH_OK"
  # перевод действительно в сборке: объект собран из .rs, и в архиве lib/math — он, а не int_pow.o
  { echo "  $h: int_pow_rs.o $( [ -f "$BD/lib/math/int_pow_rs.o" ] && echo собран || echo 'НЕ собран' );" \
         "в built-in.a: $(ar t "$BD/lib/math/built-in.a" 2>/dev/null | grep int_pow | tr '\n' ' ')"; \
    nm "$BD/lib/math/int_pow_rs.o" 2>/dev/null | grep " int_pow$" | sed "s/^/  символ: /"; } | tee -a "$OUT/probe.log"
done
echo "всего: $(( $(date +%s) - T0 )) с" | tee -a "$OUT/probe.log"
