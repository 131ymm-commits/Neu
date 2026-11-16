#!/bin/bash
# OCDIV-01: проверка кода извлечения — тесты с --real и сухой прогон на крошечной модели (hf-internal-testing), до пилота.
# Повтор 2: ревизия модели — хеш коммита с Hugging Face (HfApi.model_info), загрузка ровно по нему.
# Повтор 3 (ERRORS № 175): выборка задач pick_idx, сборка головы из двух файлов, совпадение ошибок, поправка на точность, порог в масштабе теста.
set -euo pipefail
OUT="$1"
E=experiments/2026-11-16_OCDIV-01
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 -c "import torch, transformers, numpy, sys, os; print('версии:', sys.version.split()[0], torch.__version__, transformers.__version__, numpy.__version__, '| ядер', os.cpu_count())"
python3 $E/test_ocdiv.py --real > "$OUT/tests_full.log" 2>&1 || true
grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"
