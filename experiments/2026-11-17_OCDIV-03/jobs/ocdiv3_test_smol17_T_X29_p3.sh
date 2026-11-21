#!/bin/bash
# OCDIV-03 «тысячи»: тест, HuggingFaceTB/SmolLM2-1.7B-Instruct@31b70e2e869a7173562077fd711b654946d38674, среда T_X29_p3, 2200 задач, p = 3. Файл создан make_jobs3.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E2=experiments/2026-11-17_OCDIV-02
E=experiments/2026-11-17_OCDIV-03
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
python3 $E2/ocdiv2_extract.py --phase test2 --model HuggingFaceTB/SmolLM2-1.7B-Instruct --revision 31b70e2e869a7173562077fd711b654946d38674 --envs T_X29_p3 --out "$OUT" --bs 16
