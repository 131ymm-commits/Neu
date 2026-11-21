#!/bin/bash
# OCDIV-01 «ОЦЕНЩИК-РАЗНЫЕ-ГОЛОВЫ»: тест, allenai/OLMo-2-0425-1B-Instruct@48d788eca847d4d7548f375ad03d3c9312f6139e, среда X6_p2 OCPOST-01. Файл создан make_jobs.py; одна голова — одно задание (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-16_OCDIV-01
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
python3 $E/ocdiv_extract.py --source test --model allenai/OLMo-2-0425-1B-Instruct --revision 48d788eca847d4d7548f375ad03d3c9312f6139e --envs X6_p2 --out "$OUT" --bs 16
