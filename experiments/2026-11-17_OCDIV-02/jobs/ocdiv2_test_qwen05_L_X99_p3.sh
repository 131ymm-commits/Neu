#!/bin/bash
# OCDIV-02 «ОЦЕНЩИК-ТРУДНЫЙ-СДВИГ»: тест, Qwen/Qwen2.5-0.5B-Instruct@7ae557604adf67be50417f59c2c2f167def9a775, среда L_X99_p3, 2200 задач, p = 3. Файл создан make_jobs2.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-17_OCDIV-02
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
python3 $E/ocdiv2_extract.py --phase test2 --model Qwen/Qwen2.5-0.5B-Instruct --revision 7ae557604adf67be50417f59c2c2f167def9a775 --envs L_X99_p3 --out "$OUT" --bs 16
