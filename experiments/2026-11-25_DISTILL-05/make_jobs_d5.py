#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-05: шаблоны заданий (процессор раннера, без ключей). Шаблоны — в jobs/ (в хешах регистрации); в gha_par/ их копируют только при
запуске, в ходе по уведомлению.
  python3 make_jobs_d5.py test --dir DIR    — 56 заданий: 7 голов × 8 сред test7 (по 1100 свежих задач) и 2 повтора на детерминизм
  python3 make_jobs_d5.py pilot --dir DIR   — пилот на уже виденных пятизначных суммах (new5 DISTILL-02, L_X99 построения)"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'experiments/2026-11-16_OCDIV-01'))
import distill05_extract as X5  # noqa: E402
import ocdiv  # noqa: E402

KEY = {'Qwen2.5-0.5B-Instruct': 'qwen05', 'Qwen2.5-1.5B-Instruct': 'qwen15', 'SmolLM2-1.7B-Instruct': 'smol17', 'Falcon3-1B-Instruct': 'falcon1',
       'OLMo-2-0425-1B-Instruct': 'olmo1', 'SmolLM2-360M-Instruct': 'smol360', 'TinyLlama-1.1B-Chat-v1.0': 'tinyllama'}   # как в make_jobs_d4.py
HEAD = """#!/bin/bash
# DISTILL-05 «ТОКЕН-ОПЕРАТОРЫ»: {what}. Файл создан make_jobs_d5.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-25_DISTILL-05
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
"""
TORCH = """python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
"""
PILOT = """OUT=$(realpath "$OUT")
E2=experiments/2026-11-18_DISTILL-02
python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 -c "import numpy, scipy, platform; print('версии: python', platform.python_version(), 'numpy', numpy.__version__, 'scipy', scipy.__version__)" | tee "$OUT/versions.txt"
python3 $E/test_scales_d5.py > "$OUT/tests.log" 2>&1 || true
grep -E "^✗|провалов" "$OUT/tests.log" | tail -3
grep -q "провалов: 0" "$OUT/tests.log"
python3 $E2/distill02.py merge4 "$OUT/c_L_p3" pilot3 length gha_out/ocdiv4_pilot_*
python3 $E2/distill02.py merge4 "$OUT/c_L_t3" test3 length gha_out/ocdiv4_test_*
python3 $E2/distill02.py merge_d2 "$OUT/t_T_n" new5 thousands gha_out/distill02_test_*
cat > "$OUT/spec.json" <<SPEC
{"sets": {"new5": ["$OUT/t_T_n"], "длина-построение": ["$OUT/c_L_p3", "$OUT/c_L_t3"]}, "B": 400}
SPEC
python3 $E/scales_d5.py pilot "$OUT/pilot.json" "$OUT/spec.json" | tee "$OUT/pilot.log"
rm -rf "$OUT"/c_* "$OUT"/t_*
"""
REP_N, SEED_REP = 2, 9_950_100


def write(name, what, body, dst):
    p = os.path.join(dst, f'{name}.sh')
    open(p, 'w', encoding='utf-8').write(HEAD.format(what=what) + body)
    return p


def extract(nm, env):
    repo, rev = ocdiv.CROWD[nm].split('@')
    return TORCH + f"python3 $E/distill05_extract.py --phase test7 --model {repo} --revision {rev} --envs {env} --out \"$OUT\" --bs 16\n"


def all_jobs():
    return [(nm, e['name']) for nm in ocdiv.CROWD for e in X5.envs_d5()]


def main():
    a = sys.argv[1:]
    if not a or '--dir' not in a:
        raise SystemExit(__doc__)
    mode, dst = a[0], os.path.abspath(a[a.index('--dir') + 1])
    os.makedirs(dst, exist_ok=True)
    out = []
    if mode == 'test':
        import numpy as np
        allj = all_jobs()
        for nm, env in allj:
            out.append(write(f'distill05_test_{KEY[nm]}_{env}', f'тест, {ocdiv.CROWD[nm]}, среда {env} (фаза test7), 1100 свежих задач', extract(nm, env), dst))
        for i in sorted(np.random.default_rng(SEED_REP).choice(len(allj), REP_N, replace=False)):
            nm, env = allj[i]
            out.append(write(f'distill05_rep_{KEY[nm]}_{env}', f'повтор задания distill05_test_{KEY[nm]}_{env} на другом раннере (детерминизм, описательно)',
                             extract(nm, env), dst))
    elif mode == 'pilot':
        out.append(write('distill05_pilot', 'пилот (описательно, до PREREG): доли масштабов «прочих» смещений по головам на уже виденных пятизначных '
                         'суммах (new5 DISTILL-02, L_X99 построения), мощность правил для 8 сред теста', PILOT, dst))
    else:
        raise SystemExit(__doc__)
    print('записано', len(out), 'файлов в', dst)
    return 0


if __name__ == '__main__':
    sys.exit(main())
