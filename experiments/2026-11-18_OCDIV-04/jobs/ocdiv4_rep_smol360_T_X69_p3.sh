#!/bin/bash
# OCDIV-04 «СОВПАДЕНИЕ-СМЕЩЕНИЙ»: повтор задания ocdiv4_test_smol360_T_X69_p3 на другом раннере (детерминизм, описательно). Файл создан make_jobs4.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-18_OCDIV-04
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
python3 $E/ocdiv4_extract.py --phase test3 --model HuggingFaceTB/SmolLM2-360M-Instruct --revision a10cc1512eabd3dde888204e902eca88bddb4951 --envs T_X69_p3 --out "$OUT" --bs 16
