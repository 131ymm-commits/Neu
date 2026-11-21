#!/bin/bash
# OCDIV-04 «СОВПАДЕНИЕ-СМЕЩЕНИЙ»: тест, allenai/OLMo-2-0425-1B-Instruct@48d788eca847d4d7548f375ad03d3c9312f6139e, среда T_X19_p3, 2200 задач с места 3400, p = 3. Файл создан make_jobs4.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-18_OCDIV-04
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
python3 $E/ocdiv4_extract.py --phase test3 --model allenai/OLMo-2-0425-1B-Instruct --revision 48d788eca847d4d7548f375ad03d3c9312f6139e --envs T_X19_p3 --out "$OUT" --bs 16
