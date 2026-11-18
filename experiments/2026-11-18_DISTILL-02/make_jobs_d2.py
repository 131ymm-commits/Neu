#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-02: файлы заданий теста (процессор раннера GitHub Actions, без ключей). Пуш новых файлов в gha_par/ запускает их на neu-par.
  python3 make_jobs_d2.py test --dir DIR       — 105 заданий извлечения: 7 голов × (11 сред test5 + 4 среды new5), по 2200 задач,
                                                 и 3 повтора на детерминизм
  python3 make_jobs_d2.py sum_test --dir DIR   — шаблон анализа теста
Папка обязательна (ERRORS № 198). Шаблоны — в jobs/ (в хешах регистрации); в gha_par/ их копируют только при запуске."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import distill02 as D  # noqa: E402
import distill02_extract as XD  # noqa: E402

V = D.C4.V
KEY = {'Qwen2.5-0.5B-Instruct': 'qwen05', 'Qwen2.5-1.5B-Instruct': 'qwen15', 'SmolLM2-1.7B-Instruct': 'smol17', 'Falcon3-1B-Instruct': 'falcon1',
       'OLMo-2-0425-1B-Instruct': 'olmo1', 'SmolLM2-360M-Instruct': 'smol360', 'TinyLlama-1.1B-Chat-v1.0': 'tinyllama'}   # как в make_jobs4.py
HEAD = """#!/bin/bash
# DISTILL-02 «ПРОГРАММА-ГОЛОВЫ»: {what}. Файл создан make_jobs_d2.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-18_DISTILL-02
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
"""
TORCH = """python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
"""
REP_N = 3
SEED_REP = 9_920_000


def write(name, what, body, dst):
    p = os.path.join(dst, f'{name}.sh')
    open(p, 'w', encoding='utf-8').write(HEAD.format(what=what) + body)
    return p


def extract(nm, phase, env):
    repo, rev = V.CROWD[nm].split('@')
    return TORCH + f"python3 $E/distill02_extract.py --phase {phase} --model {repo} --revision {rev} --envs {env} --out \"$OUT\" --bs 16\n"


def all_jobs():
    return [(nm, ph, e['name']) for ph in XD.PHASES5 for nm in V.CROWD for e in XD.envs_d2(ph)]


def rep_jobs():
    """Три задания из 105 — зерно SEED_REP, по упорядоченному списку (как OCDIV-04)."""
    import numpy as np
    allj = all_jobs()
    return [allj[i] for i in sorted(np.random.default_rng(SEED_REP).choice(len(allj), REP_N, replace=False))]


def main():
    a = sys.argv[1:]
    if not a or '--dir' not in a:
        raise SystemExit(__doc__)
    mode, dst = a[0], os.path.abspath(a[a.index('--dir') + 1])
    os.makedirs(dst, exist_ok=True)
    out = []
    if mode == 'test':
        for nm, ph, env in all_jobs():
            out.append(write(f"distill02_test_{KEY[nm]}_{env}", f"тест, {V.CROWD[nm]}, среда {env} (фаза {ph}), 2200 свежих задач",
                             extract(nm, ph, env), dst))
        for nm, ph, env in rep_jobs():
            out.append(write(f"distill02_rep_{KEY[nm]}_{env}", f"повтор задания distill02_test_{KEY[nm]}_{env} на другом раннере (детерминизм, описательно)",
                             extract(nm, ph, env), dst))
    elif mode == 'sum_test':
        raise SystemExit('шаблон анализа пишется после PREREG')
    else:
        raise SystemExit(__doc__)
    print(f'записано {len(out)} файлов в {os.path.relpath(dst, ROOT)}')


if __name__ == '__main__':
    main()
