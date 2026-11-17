#!/bin/bash
# OCDIV-03 «тысячи»: тест, allenai/OLMo-2-0425-1B-Instruct@48d788eca847d4d7548f375ad03d3c9312f6139e, среда T_X59_p3, 2200 задач, p = 3. Файл создан make_jobs3.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E2=experiments/2026-11-17_OCDIV-02
E=experiments/2026-11-17_OCDIV-03
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
python3 $E2/ocdiv2_extract.py --phase test2 --model allenai/OLMo-2-0425-1B-Instruct --revision 48d788eca847d4d7548f375ad03d3c9312f6139e --envs T_X59_p3 --out "$OUT" --bs 16
