#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-01: файлы заданий gha_par/ — одна голова на задание (пилот: десять сред OCSHIFT-01 по 300 задач; тест: одна среда OCPOST-01
на задание, 2200 задач). Пуш новых файлов запускает их на neu-par (до 20 раннеров одновременно).
  python3 make_jobs.py pilot            — кандидаты из HYPOTHESIS.md
  python3 make_jobs.py test NAME=REPO@REV ...   — годные головы из PREREG (ревизия — хеш коммита из пилота)"""
import os
import sys

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
CANDIDATES = {   # HYPOTHESIS.md, таблица кандидатов (имя задания → модель)
    'qwen05': 'Qwen/Qwen2.5-0.5B-Instruct', 'qwen15': 'Qwen/Qwen2.5-1.5B-Instruct',
    'smol360': 'HuggingFaceTB/SmolLM2-360M-Instruct', 'smol17': 'HuggingFaceTB/SmolLM2-1.7B-Instruct',
    'olmo1': 'allenai/OLMo-2-0425-1B-Instruct',
    'gran1': 'ibm-granite/granite-3.1-1b-a400m-instruct', 'gran2': 'ibm-granite/granite-3.1-2b-instruct',
    'falcon1': 'tiiuae/Falcon3-1B-Instruct', 'tinyllama': 'TinyLlama/TinyLlama-1.1B-Chat-v1.0',
    'lfm12': 'LiquidAI/LFM2-1.2B', 'bloomz1': 'bigscience/bloomz-1b1'}
HEAD = """#!/bin/bash
# OCDIV-01 «ОЦЕНЩИК-РАЗНЫЕ-ГОЛОВЫ»: {what}. Файл создан make_jobs.py; одна голова — одно задание (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-16_OCDIV-01
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
"""


def write(name, what, cmd):
    p = os.path.join(ROOT, 'gha_par', f'{name}.sh')
    open(p, 'w', encoding='utf-8').write(HEAD.format(what=what) + cmd + '\n')
    return p


def main():
    mode = sys.argv[1]
    out = []
    if mode == 'pilot':
        for k, repo in CANDIDATES.items():
            out.append(write(f'ocdiv_pilot_{k}', f'пилот, {repo}, десять сред OCSHIFT-01 по 300 задач',
                             f'python3 $E/ocdiv_extract.py --source pilot --model {repo} --envs all --n 300 --out "$OUT" --bs 16'))
    elif mode == 'test':
        for spec in sys.argv[2:]:
            k, rr = spec.split('=')
            repo, rev = rr.split('@')
            for X_ in range(4, 9):
                out.append(write(f'ocdiv_test_{k}_x{X_}', f'тест, {repo}@{rev}, среда X{X_}_p2 OCPOST-01',
                                 f'python3 $E/ocdiv_extract.py --source test --model {repo} --revision {rev} --envs X{X_}_p2 --out "$OUT" --bs 16'))
    print('\n'.join(os.path.relpath(p, ROOT) for p in out))


if __name__ == '__main__':
    main()
