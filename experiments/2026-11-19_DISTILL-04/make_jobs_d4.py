#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04: шаблоны заданий извлечения (процессор раннера GitHub Actions, без ключей). Шаблоны — в jobs/ (в хешах регистрации);
в gha_par/ их копируют только при запуске, в ходе по уведомлению.
  python3 make_jobs_d4.py test --dir DIR   — 63 задания: 7 голов × (8 сред test6 + L_X9999 test6L), по 2200 свежих задач;
                                            и 3 повтора на детерминизм (описательно)
  python3 make_jobs_d4.py null --dir DIR   — 4 задания нулевой серии М ≡ Т по 500 миров (совет 78, п. 5): зёрна 1000 … 2999, 4 процесса
Папка обязательна (ERRORS № 198)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'experiments/2026-11-16_OCDIV-01'))
import distill04_extract as X4  # noqa: E402
import ocdiv  # noqa: E402

KEY = {'Qwen2.5-0.5B-Instruct': 'qwen05', 'Qwen2.5-1.5B-Instruct': 'qwen15', 'SmolLM2-1.7B-Instruct': 'smol17', 'Falcon3-1B-Instruct': 'falcon1',
       'OLMo-2-0425-1B-Instruct': 'olmo1', 'SmolLM2-360M-Instruct': 'smol360', 'TinyLlama-1.1B-Chat-v1.0': 'tinyllama'}   # как в make_jobs_d2.py
HEAD = """#!/bin/bash
# DISTILL-04 «ПРОЧИЕ»: {what}. Файл создан make_jobs_d4.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-19_DISTILL-04
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
"""
TORCH = """python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
"""
REP_N = 3
SEED_REP = 9_940_100
NULL_JOBS, NULL_WORLDS, NULL_SEED0 = 4, 500, 1000
NULL_BODY = """python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 -c "import numpy, scipy, platform; print('версии: python', platform.python_version(), 'numpy', numpy.__version__, 'scipy', scipy.__version__)" | tee "$OUT/versions.txt"
echo "ревизия: $(git rev-parse HEAD) | процессоров: $(nproc)" | tee "$OUT/revision.txt"
python3 $E/test_prog_m.py > "$OUT/tests.log" 2>&1 || true
grep -E "^✗|провалов" "$OUT/tests.log" | tail -3
grep -q "провалов: 0" "$OUT/tests.log"
python3 $E/null_d4.py "$OUT/null.json" --worlds {w} --seed0 {s0} --B 4000 --n-test 2200 --n-con 400 --mix 0.5 --workers 4 > "$OUT/null.log" 2>&1
tail -2 "$OUT/null.log"
"""


def write(name, what, body, dst):
    p = os.path.join(dst, f'{name}.sh')
    open(p, 'w', encoding='utf-8').write(HEAD.format(what=what) + body)
    return p


def extract(nm, phase, env):
    repo, rev = ocdiv.CROWD[nm].split('@')
    return TORCH + f"python3 $E/distill04_extract.py --phase {phase} --model {repo} --revision {rev} --envs {env} --out \"$OUT\" --bs 16\n"


def all_jobs():
    return [(nm, ph, e['name']) for ph in X4.PHASES6 for nm in ocdiv.CROWD for e in X4.envs_d4(ph)]


def rep_jobs():
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
            out.append(write(f"distill04_test_{KEY[nm]}_{env}", f"тест, {ocdiv.CROWD[nm]}, среда {env} (фаза {ph}), 2200 свежих задач",
                             extract(nm, ph, env), dst))
        for nm, ph, env in rep_jobs():
            out.append(write(f"distill04_rep_{KEY[nm]}_{env}", f"повтор задания distill04_test_{KEY[nm]}_{env} на другом раннере (детерминизм, описательно)",
                             extract(nm, ph, env), dst))
    elif mode == 'null':
        for k in range(NULL_JOBS):
            s0 = NULL_SEED0 + k * NULL_WORLDS
            out.append(write(f'distill04_null_{k + 1}', f'нулевая серия М ≡ Т (совет 78, п. 5; PREREG §10), часть {k + 1} из {NULL_JOBS}: '
                             f'{NULL_WORLDS} миров-заглушек, зёрна {s0} … {s0 + NULL_WORLDS - 1}; вся цепочка, бутстреп B = 4000, правило m_M',
                             NULL_BODY.format(w=NULL_WORLDS, s0=s0), dst))
    else:
        raise SystemExit(__doc__)
    print('записано', len(out), 'файлов в', dst)
    return 0


if __name__ == '__main__':
    sys.exit(main())
