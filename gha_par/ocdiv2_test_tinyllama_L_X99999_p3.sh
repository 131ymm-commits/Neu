#!/bin/bash
# OCDIV-02 «ОЦЕНЩИК-ТРУДНЫЙ-СДВИГ»: тест, TinyLlama/TinyLlama-1.1B-Chat-v1.0@fe8a4ea1ffedaf415f4da2f062534de366a451e6, среда L_X99999_p3, 2200 задач, p = 3. Файл создан make_jobs2.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-17_OCDIV-02
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
python3 $E/ocdiv2_extract.py --phase test2 --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 --revision fe8a4ea1ffedaf415f4da2f062534de366a451e6 --envs L_X99999_p3 --out "$OUT" --bs 16
