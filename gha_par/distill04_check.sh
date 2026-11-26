#!/bin/bash
# DISTILL-04 «ПРОЧИЕ»: проверка кода на раннере — тесты на заглушках (программа-М, контроли совета 77, сухой прогон пилота; разведка).
# Данных голов не читает. Пилот на test5 — отдельным заданием, в ходе по уведомлению этого (CLAUDE.md, ERRORS № 31, 53).
set -euo pipefail
OUT=$(realpath "$1")
E4=experiments/2026-11-19_DISTILL-04
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 -c "import numpy, scipy, platform; print('версии: python', platform.python_version(), 'numpy', numpy.__version__, 'scipy', scipy.__version__)" | tee "$OUT/versions.txt"
python3 $E4/test_prog_m.py > "$OUT/tests_prog_m.log" 2>&1 || true
python3 $E4/test_explore_d4.py > "$OUT/tests_explore.log" 2>&1 || true
grep -h -E "^✗|провалов" "$OUT/tests_prog_m.log" "$OUT/tests_explore.log" | tee "$OUT/tests.log"
grep -q "провалов: 0" "$OUT/tests_prog_m.log" && grep -q "провалов: 0" "$OUT/tests_explore.log"
