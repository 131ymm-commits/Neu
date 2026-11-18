#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-04: файлы заданий (процессор раннера GitHub Actions, без ключей). Пуш новых файлов в gha_par/ запускает их на neu-par.
  python3 make_jobs4.py pilot --dir DIR      — 77 заданий пилота: 7 голов × 11 сред (8 «тысяч», 3 «длины»), фаза pilot3, 600 задач
  python3 make_jobs4.py sum_pilot --dir DIR  — разбор пилота: тесты кода, сборка merge4 по семействам, ocdiv4.py pilot (B = 1000, 4 процесса)
  python3 make_jobs4.py sum_pilot2 --dir DIR — повторный разбор по HYPOTHESIS-ADDENDUM и сверка с первым разбором до бита
  python3 make_jobs4.py test --dir DIR       — шаблоны теста: 77 заданий фазы test3 (2200 задач) и 3 повтора на детерминизм
  python3 make_jobs4.py sum_test --dir DIR   — шаблон анализа теста
Папка обязательна (ERRORS № 198: умолчание положило задание не туда). Пилот — в gha_par/ (не регистрируется), тест и анализ теста — в jobs/
(в хешах регистрации; в gha_par/ их копируют только при запуске)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import ocdiv4 as C  # noqa: E402

X4, V = C.X4, C.V
KEY = {'Qwen2.5-0.5B-Instruct': 'qwen05', 'Qwen2.5-1.5B-Instruct': 'qwen15', 'SmolLM2-1.7B-Instruct': 'smol17', 'Falcon3-1B-Instruct': 'falcon1',
       'OLMo-2-0425-1B-Instruct': 'olmo1', 'SmolLM2-360M-Instruct': 'smol360', 'TinyLlama-1.1B-Chat-v1.0': 'tinyllama'}   # как в make_jobs3.py
HEAD = """#!/bin/bash
# OCDIV-04 «СОВПАДЕНИЕ-СМЕЩЕНИЙ»: {what}. Файл создан make_jobs4.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E=experiments/2026-11-18_OCDIV-04
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
"""
TORCH = """python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
"""
SCI = """python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
"""
TESTS = ('python3 tools/test_raw_status.py | tee "$OUT/raw_status_test.log" | tail -1\n'
         'python3 $E/test_ocdiv4.py > "$OUT/tests_full.log" 2>&1 || true\n'
         'grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"\n'
         'grep -q "провалов: 0" "$OUT/tests.log"\n')
REP_N = 3


def write(name, what, body, dst):
    p = os.path.join(dst, f'{name}.sh')
    open(p, 'w', encoding='utf-8').write(HEAD.format(what=what) + body)
    return p


def extract(nm, env, phase):
    repo, rev = V.CROWD[nm].split('@')
    return TORCH + f"python3 $E/ocdiv4_extract.py --phase {phase} --model {repo} --revision {rev} --envs {env} --out \"$OUT\" --bs 16\n"


def rep_jobs():
    """ДЕТЕРМИНИЗМ-НА-3: три задания теста из 77 — зерно SEED_REP4, по упорядоченному списку (как ocdiv3.rep_jobs)."""
    import numpy as np
    allj = [(nm, e['name']) for nm in V.CROWD for e in X4.envs_ocdiv4('test3')]
    return [allj[i] for i in sorted(np.random.default_rng(C.SEED_REP4).choice(len(allj), REP_N, replace=False))]


def main():
    a = sys.argv[1:]
    mode = a[0]
    if '--dir' not in a:
        raise SystemExit('нужна папка: --dir gha_par (пилот) или --dir experiments/2026-11-18_OCDIV-04/jobs (тест)')
    dst = os.path.abspath(a[a.index('--dir') + 1])
    os.makedirs(dst, exist_ok=True)
    out = []
    if mode == 'pilot':
        for nm in V.CROWD:
            for e in X4.envs_ocdiv4('pilot3'):
                out.append(write(f"ocdiv4_pilot_{KEY[nm]}_{e['name']}", f"пилот, {V.CROWD[nm]}, среда {e['name']}, 600 задач с места 6000, p = {e['p']}",
                                 extract(nm, e['name'], 'pilot3'), dst))
    elif mode == 'sum_pilot':
        out.append(write('ocdiv4_sum_pilot', 'разбор пилота — после вывода всех 77 заданий; тесты кода и замка № 180, сборка merge4 по семействам, '
                         'невырожденность, мощность Р1-Т, Р1-Л, Р2-Т (частей А и Б), вброс и годность N3c (B = 1000, 4 процесса)',
                         SCI + TESTS +
                         'python3 $E/ocdiv4.py merge "$OUT/m_T" pilot3 thousands gha_out/ocdiv4_pilot_*\n'
                         'python3 $E/ocdiv4.py merge "$OUT/m_L" pilot3 length gha_out/ocdiv4_pilot_*\n'
                         'python3 $E/ocdiv4.py pilot "$OUT/pilot.json" "$OUT/m_T" "$OUT/m_L" --boot 1000 --workers 4\n'
                         'rm -rf "$OUT/m_T" "$OUT/m_L"          # сборки восстанавливаются из gha_out/ocdiv4_pilot_*/ той же командой\n', dst))
    elif mode == 'sum_pilot2':
        out.append(write('ocdiv4_sum_pilot2', 'повторный разбор пилота по HYPOTHESIS-ADDENDUM (ВБРОС-ПО-ЗАДАЧАМ, двусторонняя мощность Р2-Т; '
                         'ERRORS № 201, 202): тесты кода, сборка merge4, ocdiv4.py pilot (B = 1000), сверка с первым разбором до бита',
                         SCI + TESTS +
                         'python3 $E/ocdiv4.py merge "$OUT/m_T" pilot3 thousands gha_out/ocdiv4_pilot_*\n'
                         'python3 $E/ocdiv4.py merge "$OUT/m_L" pilot3 length gha_out/ocdiv4_pilot_*\n'
                         'python3 $E/ocdiv4.py pilot "$OUT/pilot.json" "$OUT/m_T" "$OUT/m_L" --boot 1000 --workers 4\n'
                         'python3 $E/ocdiv4.py compare_pilots "$OUT/pilot.json" gha_out/ocdiv4_sum_pilot/pilot.json | tee "$OUT/compare.log"\n'
                         'rm -rf "$OUT/m_T" "$OUT/m_L"\n', dst))
    elif mode == 'sum_pilot3':
        out.append(write('ocdiv4_sum_pilot3', 'третий разбор пилота — для совета 72: запасной нуль N0 со стратами c1 (по букве HYPOTHESIS §7) и его мощность; '
                         'всё прежнее сверяется со вторым разбором до бита',
                         SCI + TESTS +
                         'python3 $E/ocdiv4.py merge "$OUT/m_T" pilot3 thousands gha_out/ocdiv4_pilot_*\n'
                         'python3 $E/ocdiv4.py merge "$OUT/m_L" pilot3 length gha_out/ocdiv4_pilot_*\n'
                         'python3 $E/ocdiv4.py pilot "$OUT/pilot.json" "$OUT/m_T" "$OUT/m_L" --boot 1000 --workers 4\n'
                         'python3 $E/ocdiv4.py compare_pilots "$OUT/pilot.json" gha_out/ocdiv4_sum_pilot2/pilot.json | tee "$OUT/compare.log"\n'
                         'rm -rf "$OUT/m_T" "$OUT/m_L"\n', dst))
    elif mode == 'test':
        for nm in V.CROWD:
            for e in X4.envs_ocdiv4('test3'):
                out.append(write(f"ocdiv4_test_{KEY[nm]}_{e['name']}", f"тест, {V.CROWD[nm]}, среда {e['name']}, 2200 задач с места 3400, p = {e['p']}",
                                 extract(nm, e['name'], 'test3'), dst))
        for nm, env in rep_jobs():
            out.append(write(f"ocdiv4_rep_{KEY[nm]}_{env}", f"повтор задания ocdiv4_test_{KEY[nm]}_{env} на другом раннере (детерминизм, описательно)",
                             extract(nm, env, 'test3'), dst))
    elif mode == 'sum_test':
        out.append(write('ocdiv4_sum_test', 'анализ теста — после вывода всех 77 заданий и 3 повторов; сверка хешей регистрации, тесты кода и замка № 180, '
                         'сборка, Р1-Т, Р1-Л, Р2-Т и описательное (B = 10 000, 4 процесса)',
                         SCI + 'python3 $E/prereg_hashes4.py --verify --jobs\n' + TESTS +
                         'python3 $E/ocdiv4.py merge "$OUT/m_T" test3 thousands gha_out/ocdiv4_test_*\n'
                         'python3 $E/ocdiv4.py merge "$OUT/m_L" test3 length gha_out/ocdiv4_test_*\n'
                         'python3 $E/ocdiv4.py test "$OUT/analysis.json" "$OUT/m_T" "$OUT/m_L" gha_out/ocdiv4_sum_pilot3/pilot.json --boot 10000 --workers 4\n'
                         'echo "== прибор"; python3 experiments/2026-11-17_OCDIV-02/trunc_check.py "$OUT/trunc.json" "gha_out/ocdiv4_test_*/answers_*.json" | tail -3\n'
                         'rm -rf "$OUT/m_T" "$OUT/m_L"\n', dst))
    else:
        raise SystemExit(__doc__)
    print(f'записано {len(out)} файлов в {os.path.relpath(dst, ROOT)}')


if __name__ == '__main__':
    main()
