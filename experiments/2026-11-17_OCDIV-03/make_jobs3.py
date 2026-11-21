#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-03: файлы заданий (процессор раннера GitHub Actions, без ключей). Пуш новых файлов в gha_par/ запускает их на neu-par.
  python3 make_jobs3.py pilot [--dir DIR]     — тесты кода и разбор пилота 2 «тысяч» (модели голов, кросс-подгонка, мощность, Т4 из формул)
  python3 make_jobs3.py pilot_n2 [--dir DIR]  — то же кодом после правок совета 70 (Н2: правило чтения П2 на пилоте)
  python3 make_jobs3.py test [--dir DIR]      — шаблоны теста: 35 заданий (7 голов × 5 сред «тысяч», 2200 задач, фаза test2) и 3 повтора
  python3 make_jobs3.py sum_test [--dir DIR]  — шаблон анализа теста (после вывода всех 38 заданий)
Шаблоны теста и анализа лежат в jobs/ (в хешах регистрации); в gha_par/ их копируют только при запуске.
Извлечение — код OCDIV-02 без изменений (ocdiv2_extract.py, фаза test2); головы и ревизии — ocdiv.CROWD (регистрация OCDIV-01 c626aa32)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import ocdiv3 as T  # noqa: E402

D2, V = T.D2, T.V
KEY = {'Qwen2.5-0.5B-Instruct': 'qwen05', 'Qwen2.5-1.5B-Instruct': 'qwen15', 'SmolLM2-1.7B-Instruct': 'smol17', 'Falcon3-1B-Instruct': 'falcon1',
       'OLMo-2-0425-1B-Instruct': 'olmo1', 'SmolLM2-360M-Instruct': 'smol360', 'TinyLlama-1.1B-Chat-v1.0': 'tinyllama'}   # как в make_jobs2.py
HEAD = """#!/bin/bash
# OCDIV-03 «тысячи»: {what}. Файл создан make_jobs3.py (процессор раннера, без ключей).
set -euo pipefail
OUT="$1"
E2=experiments/2026-11-17_OCDIV-02
E=experiments/2026-11-17_OCDIV-03
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
"""
TORCH = """python3 -m pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.11.0
python3 -m pip install -q transformers==5.20.2 numpy==2.5.3
"""
SCI = """python3 -m pip install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 threadpoolctl==3.8.0
"""
TESTS = ('python3 tools/test_raw_status.py | tee "$OUT/raw_status_test.log" | tail -1\n'
         'python3 $E/test_ocdiv3.py > "$OUT/tests_full.log" 2>&1 || true\n'
         'grep -E "^✓|^✗|провалов" "$OUT/tests_full.log" | tee "$OUT/tests.log"\n'
         'grep -q "провалов: 0" "$OUT/tests.log"\n')


def write(name, what, body, dst):
    p = os.path.join(dst, f'{name}.sh')
    open(p, 'w', encoding='utf-8').write(HEAD.format(what=what) + body)
    return p


def extract(nm, env):
    repo, rev = V.CROWD[nm].split('@')
    return TORCH + f"python3 $E2/ocdiv2_extract.py --phase {T.TEST_PHASE} --model {repo} --revision {rev} --envs {env} --out \"$OUT\" --bs 16\n"


def main():
    a = sys.argv[1:]
    mode = a[0]
    dst = os.path.abspath(a[a.index('--dir') + 1]) if '--dir' in a else (os.path.join(ROOT, 'gha_par') if mode in ('pilot', 'pilot_n2') else os.path.join(HERE, 'jobs'))
    os.makedirs(dst, exist_ok=True)
    out = []
    if mode in ('pilot', 'pilot_n2'):
        name, what = (('ocdiv3_pilot', 'тесты кода на заглушках и разбор пилота 2 «тысяч» — модели голов (признаки входа), кросс-подгонка, Т4, Т4ᵈ, '
                       'Т4-ID, мощность правил и условий, Т4 из формул по задачам теста; сверка блока N0 до бита с разбором пилота OCDIV-02')
                      if mode == 'pilot' else
                      ('ocdiv3_pilot_n2', 'совет 70, Н2 — разбор пилота 2 «тысяч» кодом после правок совета: правило чтения П2 (Н1) по пяти средам '
                       'с кросс-подгонкой d̂, различение страт, мощность и при τ из верхней границы; тесты кода с замками Н6'))
        out.append(write(name, what, SCI + TESTS +
                         'python3 $E2/ocdiv2.py merge "$OUT/m_pilot2" pilot2 thousands gha_out/ocdiv2_pilot2_*\n'
                         'python3 $E/ocdiv3.py pilot "$OUT/pilot.json" "$OUT/m_pilot2" --boot 1000 --workers 4\n'
                         'rm -rf "$OUT/m_pilot2"          # сборка восстанавливается из gha_out/ocdiv2_pilot2_*/ той же командой\n', dst))
    elif mode == 'test':
        for nm in V.CROWD:
            for e in D2.envs_ocdiv2(T.TEST_PHASE, (T.FAMILY,)):
                out.append(write(f"ocdiv3_test_{KEY[nm]}_{e['name']}", f"тест, {V.CROWD[nm]}, среда {e['name']}, 2200 задач, p = {e['p']}",
                                 extract(nm, e['name']), dst))
        for nm, env in T.rep_jobs():                         # ДЕТЕРМИНИЗМ-НА-3: те же задания под другими именами (описательно)
            out.append(write(f"ocdiv3_rep_{KEY[nm]}_{env}", f"повтор задания ocdiv3_test_{KEY[nm]}_{env} на другом раннере (детерминизм, описательно)",
                             extract(nm, env), dst))
    elif mode == 'sum_test':
        out.append(write('ocdiv3_sum_test', 'анализ теста — после вывода всех 35 заданий теста и 3 повторов; сверка хешей регистрации и копий '
                         'заданий, тесты кода и замка № 180, сборка, П1–П3 и описательное (B = 10 000, описательные нули — 2000, 4 процесса), прибор',
                         SCI + 'python3 $E/prereg_hashes3.py --verify --jobs\n' + TESTS +
                         'echo "== сборка"; python3 $E2/ocdiv2.py merge "$OUT/merged" test2 thousands gha_out/ocdiv3_test_*\n'
                         'python3 $E2/ocdiv2.py merge "$OUT/m_pilot2" pilot2 thousands gha_out/ocdiv2_pilot2_*\n'
                         'echo "== тест"; python3 $E/ocdiv3.py test "$OUT/analysis.json" "$OUT/merged" "$OUT/m_pilot2" gha_out/ocdiv3_pilot_n2/pilot.json '
                         '--boot 10000 --boot-descr 2000 --workers 4\n'
                         'echo "== прибор"; python3 $E2/trunc_check.py "$OUT/trunc.json" "gha_out/ocdiv3_test_*/answers_*.json" | tail -3\n'
                         'rm -rf "$OUT/merged" "$OUT/m_pilot2"          # сборки восстанавливаются из gha_out/ той же командой\n', dst))
    print('\n'.join(os.path.relpath(p, ROOT) for p in out))


if __name__ == '__main__':
    main()
