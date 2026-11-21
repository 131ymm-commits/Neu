#!/bin/bash
# OCDIV-01 «ОЦЕНЩИК-РАЗНЫЕ-ГОЛОВЫ»: тест, HuggingFaceTB/SmolLM2-360M-Instruct@a10cc1512eabd3dde888204e902eca88bddb4951, среда X8_p2 OCPOST-01. Файл создан make_jobs.py; одна голова — одно задание (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-16_OCDIV-01
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
python3 $E/ocdiv_extract.py --source test --model HuggingFaceTB/SmolLM2-360M-Instruct --revision a10cc1512eabd3dde888204e902eca88bddb4951 --envs X8_p2 --out "$OUT" --bs 16
