#!/bin/bash
# DISTILL-04 «ПРОЧИЕ»: тест, HuggingFaceTB/SmolLM2-1.7B-Instruct@31b70e2e869a7173562077fd711b654946d38674, среда T_X74_p3 (фаза test6), 2200 свежих задач. Файл создан make_jobs_d4.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-19_DISTILL-04
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
python3 $E/distill04_extract.py --phase test6 --model HuggingFaceTB/SmolLM2-1.7B-Instruct --revision 31b70e2e869a7173562077fd711b654946d38674 --envs T_X74_p3 --out "$OUT" --bs 16
