#!/bin/bash
# OCSHIFT-01: обёртка задания GitHub Actions для анализа теста — шаблон (входит в хеши регистрации).
# В день теста копируется без изменений в gha_jobs/ocshift_test.sh одним коммитом с сырым выводом Kaggle;
# prereg_hashes.py --verify сверяет копию с этим шаблоном.
set -euo pipefail
bash experiments/2026-11-15_OCSHIFT-01/gha_ocshift_test.sh "$1"
