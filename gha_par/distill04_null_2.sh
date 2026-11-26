#!/bin/bash
# DISTILL-04 «ПРОЧИЕ»: нулевая серия М ≡ Т (совет 78, п. 5; PREREG §10), часть 2 из 4: 500 миров-заглушек, зёрна 1500 … 1999; вся цепочка, бутстреп B = 4000, правило m_M. Файл создан make_jobs_d4.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-19_DISTILL-04
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 -c "import numpy, scipy, platform; print('версии: python', platform.python_version(), 'numpy', numpy.__version__, 'scipy', scipy.__version__)" | tee "$OUT/versions.txt"
echo "ревизия: $(git rev-parse HEAD) | процессоров: $(nproc)" | tee "$OUT/revision.txt"
python3 $E/test_prog_m.py > "$OUT/tests.log" 2>&1 || true
grep -E "^✗|провалов" "$OUT/tests.log" | tail -3
grep -q "провалов: 0" "$OUT/tests.log"
python3 $E/null_d4.py "$OUT/null.json" --worlds 500 --seed0 1500 --B 4000 --n-test 2200 --n-con 400 --mix 0.5 --workers 4 > "$OUT/null.log" 2>&1
tail -2 "$OUT/null.log"
