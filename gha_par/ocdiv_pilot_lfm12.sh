#!/bin/bash
# OCDIV-01 «ОЦЕНЩИК-РАЗНЫЕ-ГОЛОВЫ»: пилот, LiquidAI/LFM2-1.2B, десять сред OCSHIFT-01 по 300 задач. Файл создан make_jobs.py; одна голова — одно задание (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-16_OCDIV-01
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
python3 $E/ocdiv_extract.py --source pilot --model LiquidAI/LFM2-1.2B --envs all --n 300 --out "$OUT" --bs 16
