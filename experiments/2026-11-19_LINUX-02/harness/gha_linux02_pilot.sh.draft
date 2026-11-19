#!/bin/bash
# LINUX-02, пилот (PLAN-PILOT.md; уточнения до оценки — DEVIATIONS.md; числа — harness/README.md). Одной цепочкой, чтобы
# отбор модулей сработал по правилу до того, как я увижу промежуточные числа:
#   1) проверка обвязки — оригиналы: KUnit, оригинал против себя на всех потоках правды (вердикт и независимый поиск),
#      то же под UBSan; не прошла — цепочка остановлена;
#   2) оценка переводов обеих версий пилота — pilot (поручения v1, описательно) и pilot2 (поручения test, DEVIATIONS пп. 9–10):
#      rustc, KUnit, сравнение с оригиналом (вердикт: 20 000 обычных и 20 000 крайних проверок на функцию);
#   3) мутанты шести модулей на фазе pilot2: основы, вердикт и независимый поиск у каждого мутанта;
#   4) отбор модулей в тест — пять условий, механически (harness/select_modules.py); оценка неполна — отбора нет.
# Процессор раннера, без ключей; головы не вызываются. rustc закреплён: 1.97.0, как в сессии (разбор, Н16).
set -uo pipefail
OUT=$(realpath "$1")
E=experiments/2026-11-19_LINUX-02
if command -v rustup >/dev/null; then
  rustup set profile minimal >/dev/null 2>&1; rustup toolchain install 1.97.0 >/dev/null 2>&1 && rustup default 1.97.0 >/dev/null
else
  curl -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain 1.97.0 >/dev/null
fi
source "$HOME/.cargo/env" 2>/dev/null || true
{ gcc --version | head -1; rustc --version; nproc; git rev-parse HEAD; } | tee "$OUT/versions.txt"
cd $E || exit 1
T0=$(date +%s)
python3 harness/run.py check "$OUT/check.json" | tee "$OUT/check.log" || { echo "проверка обвязки не прошла — цепочка остановлена" | tee -a "$OUT/check.log"; exit 1; }
for ph in pilot pilot2; do
  python3 harness/run.py eval "$OUT/eval_$ph.json" $ph | tee "$OUT/eval_$ph.log" || echo "оценка $ph: код выхода не 0" | tee -a "$OUT/eval_$ph.log"
done
mkdir -p "$OUT/mutants"
for m in errseq 842_decompress md5 random32 min_heap string_helpers; do
  python3 harness/mutants.py "$OUT/mutants/mutants_$m.json" "$m" --phase pilot2 --per-file 25 --seed 17 | tee -a "$OUT/mutants.log" \
    || echo "мутанты $m: код выхода не 0" | tee -a "$OUT/mutants.log"
done
python3 harness/select_modules.py "$OUT/check.json" "$OUT/mutants" "$OUT/select.json" --eval pilot="$OUT/eval_pilot.json" \
  --eval pilot2="$OUT/eval_pilot2.json" --default-phase pilot2 | tee "$OUT/select.log"
echo "время: $(( $(date +%s) - T0 )) с" | tee -a "$OUT/select.log"
