#!/bin/bash
# Проба открытых моделей других производителей на процессоре раннера (слово автора 16.11.2026: «Ты думаешь. Внешние ресурсы считают.
# … Попробуй их так то интегрировать в проект»). Без ключей: веса с Hugging Face без лицензионного замка. Техническая проба, не опыт
# (tools/open_probe.py): загрузка, 12 задач сложения с правдой от кода, время, уверенность по логарифмам вероятностей.
set -euo pipefail
OUT="$1"
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
python3 -c "import torch, transformers, os; print('версии:', torch.__version__, transformers.__version__, '| ядер', os.cpu_count())"
df -h / | tail -1
python3 tools/open_probe.py "$OUT"
