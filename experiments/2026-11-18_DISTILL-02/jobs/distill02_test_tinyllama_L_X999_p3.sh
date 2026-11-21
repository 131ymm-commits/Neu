#!/bin/bash
# DISTILL-02 «ПРОГРАММА-ГОЛОВЫ»: тест, TinyLlama/TinyLlama-1.1B-Chat-v1.0@fe8a4ea1ffedaf415f4da2f062534de366a451e6, среда L_X999_p3 (фаза test5), 2200 свежих задач. Файл создан make_jobs_d2.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-18_DISTILL-02
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
python3 $E/distill02_extract.py --phase test5 --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 --revision fe8a4ea1ffedaf415f4da2f062534de366a451e6 --envs L_X999_p3 --out "$OUT" --bs 16
