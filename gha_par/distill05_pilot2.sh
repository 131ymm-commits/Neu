#!/bin/bash
# DISTILL-05 «ТОКЕН-ОПЕРАТОРЫ»: пилот (описательно, до PREREG): доли масштабов «прочих» смещений по головам на уже виденных пятизначных суммах (new5 DISTILL-02, L_X99 построения), мощность правил для 8 сред теста. Файл создан make_jobs_d5.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-25_DISTILL-05
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
OUT=$(realpath "$OUT")
E2=experiments/2026-11-18_DISTILL-02
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 -c "import numpy, scipy, platform; print('версии: python', platform.python_version(), 'numpy', numpy.__version__, 'scipy', scipy.__version__)" | tee "$OUT/versions.txt"
python3 $E/test_scales_d5.py > "$OUT/tests.log" 2>&1 || true
grep -E "^✗|провалов" "$OUT/tests.log" | tail -3
grep -q "провалов: 0" "$OUT/tests.log"
python3 $E2/distill02.py merge4 "$OUT/c_L_p3" pilot3 length gha_out/ocdiv4_pilot_*
python3 $E2/distill02.py merge4 "$OUT/c_L_t3" test3 length gha_out/ocdiv4_test_*
python3 $E2/distill02.py merge_d2 "$OUT/t_T_n" new5 thousands gha_out/distill02_test_*
cat > "$OUT/spec.json" <<SPEC
{"sets": {"new5": ["$OUT/t_T_n"], "длина-построение": ["$OUT/c_L_p3", "$OUT/c_L_t3"]}, "B": 400}
SPEC
python3 $E/scales_d5.py pilot "$OUT/pilot.json" "$OUT/spec.json" | tee "$OUT/pilot.log"
rm -rf "$OUT"/c_* "$OUT"/t_*
