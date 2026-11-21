#!/bin/bash
# OCDIV-02 «ОЦЕНЩИК-ТРУДНЫЙ-СДВИГ»: пилот 2 (подсказка только из ID, HYPOTHESIS-2), tiiuae/Falcon3-1B-Instruct@28ba2251970a01dd1edc7ba7dad2eb71216ccfdf, семейство thousands, 5 сред × 400 задач, p = 1. Файл создан make_jobs2.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-17_OCDIV-02
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
python3 $E/ocdiv2_extract.py --phase pilot2 --model tiiuae/Falcon3-1B-Instruct --revision 28ba2251970a01dd1edc7ba7dad2eb71216ccfdf --envs T_X19_p1,T_X29_p1,T_X39_p1,T_X49_p1,T_X59_p1 --out "$OUT" --bs 16
