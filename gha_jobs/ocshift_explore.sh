#!/bin/bash
# OCSHIFT-01, разведка по трём готовым сдвигам (OCCOR-01, OCMIX-01, OCREP-01) — пост-хок, вердиктов не меняет.
# Считается на GitHub Actions по слову автора 15.11.2026 («все эксперименты на сторонних серверах»).
set -euo pipefail
OUT="$1"
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
python3 -c "import numpy, scipy, sklearn, sys, os; print('версии:', sys.version.split()[0], numpy.__version__, scipy.__version__, sklearn.__version__, '| ядер', os.cpu_count())"
python3 experiments/2026-11-15_OCSHIFT-01/explore_shifts.py "$OUT" --boot 400
