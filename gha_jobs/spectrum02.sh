#!/bin/bash
# SPECTRUM-02 «показатель» — основной прогон (регистрация: коммит d04db806, experiments/2026-11-14_SPECTRUM-02/PREREG-SPECTRUM-02.md).
# Обёртка: вся работа — в зарегистрированном сценарии (он входит в хеши регистрации и сверяет их перед прогоном).
set -euo pipefail
bash experiments/2026-11-14_SPECTRUM-02/gha_spectrum02.sh "$1"
