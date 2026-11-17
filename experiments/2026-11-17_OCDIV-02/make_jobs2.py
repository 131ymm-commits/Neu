#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-02: файлы заданий gha_par/ (процессор раннера GitHub Actions, без ключей). Пуш новых файлов запускает их на neu-par.
  python3 make_jobs2.py check [--dir DIR]      — проверка кода: заглушки, сухой прогон на крошечной модели, тест замка № 180
  python3 make_jobs2.py pilot [--dir DIR]      — пилот: 7 голов × 2 семейства (по заданию на голову и семейство, 5 сред × 400 задач, p = 0)
  python3 make_jobs2.py sum_pilot [--dir DIR]  — разбор пилота (после всех 14 заданий пилота): сборка, правило выбора семейства, мощность
  python3 make_jobs2.py test FAMILY [--dir DIR] — тест: 7 голов × 5 сред выбранного семейства (по заданию на голову и среду, 2200 задач, p = 2)
Головы и ревизии — ocdiv.CROWD (регистрация OCDIV-01 c626aa32)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import ocdiv2_extract as D2  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, 'experiments/2026-11-16_OCDIV-01'))
import ocdiv as V  # noqa: E402

KEY = {'Qwen2.5-0.5B-Instruct': 'qwen05', 'Qwen2.5-1.5B-Instruct': 'qwen15', 'SmolLM2-1.7B-Instruct': 'smol17', 'Falcon3-1B-Instruct': 'falcon1',
       'OLMo-2-0425-1B-Instruct': 'olmo1', 'SmolLM2-360M-Instruct': 'smol360', 'TinyLlama-1.1B-Chat-v1.0': 'tinyllama'}
HEAD = """#!/bin/bash
# OCDIV-02 «ОЦЕНЩИК-ТРУДНЫЙ-СДВИГ»: {what}. Файл создан make_jobs2.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-17_OCDIV-02
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
"""
TORCH = """python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
"""
SCI = """python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
"""


def write(name, what, body, dst):
    p = os.path.join(dst, f'{name}.sh')
    open(p, 'w', encoding='utf-8').write(HEAD.format(what=what) + body)
    return p


def main():
    a = sys.argv[1:]
    mode = a[0]
    dst = os.path.abspath(a[a.index('--dir') + 1]) if '--dir' in a else os.path.join(ROOT, 'gha_par')
    os.makedirs(dst, exist_ok=True)
    out = []
    if mode == 'check':
        out.append(write('ocdiv2_check', 'проверка кода — заглушки, сухой прогон извлечения на крошечной модели, равенство с ocdiv_extract.run, '
                         'тест замка ERRORS № 180', TORCH + SCI +
                         'python3 tools/test_raw_status.py | tee "$OUT/raw_status_test.log"\n'
                         'python3 $E/test_ocdiv2.py --real > "$OUT/tests_full.log" 2>&1 || true\n'
                         'grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"\n'
                         'grep -q "провалов: 0" "$OUT/tests.log"\n', dst))
    elif mode == 'pilot':
        for nm, spec in V.CROWD.items():
            repo, rev = spec.split('@')
            for fam, f in D2.FAMILIES.items():
                envs = ','.join(e['name'] for e in D2.envs_ocdiv2('pilot', (fam,)))
                out.append(write(f"ocdiv2_pilot_{KEY[nm]}_{f['code']}", f'пилот, {repo}@{rev}, семейство {fam}, 5 сред × 400 задач, p = 0',
                                 TORCH + f'python3 $E/ocdiv2_extract.py --phase pilot --model {repo} --revision {rev} --envs {envs} --out "$OUT" --bs 16\n', dst))
    elif mode == 'sum_pilot':
        out.append(write('ocdiv2_sum_pilot', 'разбор пилота — сборка двух семейств, правило выбора семейства (HYPOTHESIS), мощность Т1–Т4', SCI +
                         'python3 tools/test_raw_status.py | tail -1\n'
                         'python3 $E/test_ocdiv2.py > "$OUT/tests_full.log" 2>&1; grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"\n'
                         'python3 $E/ocdiv2.py merge "$OUT/m_thousands" pilot thousands gha_out/ocdiv2_pilot_*\n'
                         'python3 $E/ocdiv2.py merge "$OUT/m_length" pilot length gha_out/ocdiv2_pilot_*\n'
                         'python3 $E/ocdiv2.py pilot "$OUT/pilot.json" "$OUT/m_thousands" "$OUT/m_length" --boot 200 --workers 4\n'
                         'rm -rf "$OUT/m_thousands" "$OUT/m_length"          # сборка восстанавливается из gha_out/ocdiv2_pilot_*/ той же командой\n', dst))
    elif mode == 'test':
        fam = a[1]
        for nm, spec in V.CROWD.items():
            repo, rev = spec.split('@')
            for e in D2.envs_ocdiv2('test', (fam,)):
                out.append(write(f"ocdiv2_test_{KEY[nm]}_{e['name']}", f"тест, {repo}@{rev}, среда {e['name']}, 2200 задач, p = 2",
                                 TORCH + f"python3 $E/ocdiv2_extract.py --phase test --model {repo} --revision {rev} --envs {e['name']} --out \"$OUT\" --bs 16\n", dst))
    print('\n'.join(os.path.relpath(p, ROOT) for p in out))


if __name__ == '__main__':
    main()
