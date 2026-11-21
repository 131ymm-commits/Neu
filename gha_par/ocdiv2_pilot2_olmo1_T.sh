#!/bin/bash
# OCDIV-02 «ОЦЕНЩИК-ТРУДНЫЙ-СДВИГ»: пилот 2 (подсказка только из ID, HYPOTHESIS-2), allenai/OLMo-2-0425-1B-Instruct@48d788eca847d4d7548f375ad03d3c9312f6139e, семейство thousands, 5 сред × 400 задач, p = 1. Файл создан make_jobs2.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-17_OCDIV-02
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
python3 $E/ocdiv2_extract.py --phase pilot2 --model allenai/OLMo-2-0425-1B-Instruct --revision 48d788eca847d4d7548f375ad03d3c9312f6139e --envs T_X19_p1,T_X29_p1,T_X39_p1,T_X49_p1,T_X59_p1 --out "$OUT" --bs 16
