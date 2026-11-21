#!/bin/bash
# OCDIV-01 «ОЦЕНЩИК-РАЗНЫЕ-ГОЛОВЫ»: пилот 2, Qwen/Qwen2.5-1.5B-Instruct@989aa7980e4cf806f80c7fef2b1adb7bc71aa306, пять сред OCSHIFT-01 с p = 0, по 600 случайных задач. Файл создан make_jobs.py; одна голова — одно задание (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-16_OCDIV-01
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
python3 $E/ocdiv_extract.py --source pilot --model Qwen/Qwen2.5-1.5B-Instruct --revision 989aa7980e4cf806f80c7fef2b1adb7bc71aa306 --envs X4_p0,X5_p0,X6_p0,X7_p0,X8_p0 --n 600 --pick random --out "$OUT" --bs 16
