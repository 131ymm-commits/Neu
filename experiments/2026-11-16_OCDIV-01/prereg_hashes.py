#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-01: sha256 файлов на момент регистрации → prereg_hashes.json; --verify [--jobs] — сверка перед счётом.
В списке — код опыта, зарегистрированный код прежних опытов, на который он опирается (OCPOST-01 → OCSHIFT-01, OCINT-01 → OCREP-01 →
OCMIX-01 → OCCOR-01 → OCGEO-01), источники задач и ответов Pythia, вывод пилотов, файл workflow и шаблоны заданий теста (jobs/).
С --jobs копии шаблонов в gha_par/ (если они там есть) должны побайтно совпасть со своими шаблонами: копии кладутся в gha_par только
при запуске, поэтому сверяются лишь запущенные."""
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OWN = ['ocdiv.py', 'ocdiv_extract.py', 'make_jobs.py', 'test_ocdiv.py', 'prereg_hashes.py', 'HYPOTHESIS.md',
       '../../.github/workflows/neu-par.yml',
       '../../gha_out/ocdiv_sum_pilot2/pilot2.json', '../../gha_out/ocdiv_sum_pilot2/pilot1.json',
       '../2026-11-15_OCPOST-01/run/out/answers.json', '../2026-11-15_OCSHIFT-01/run/out/answers.json',
       '../2026-11-15_OCPOST-01/ocpost.py', '../2026-11-15_OCPOST-01/ocpost_extract.py',
       '../2026-11-15_OCSHIFT-01/analyze_ocshift.py', '../2026-11-15_OCSHIFT-01/analyze_ocshift_test.py', '../2026-11-15_OCSHIFT-01/ocshift_extract.py',
       '../2026-11-15_OCINT-01/ocint.py', '../2026-11-15_OCREP-01/analyze_ocrep.py', '../2026-11-15_OCREP-01/analyze_ocrep_test.py',
       '../2026-11-14_OCMIX-01/analyze_ocmix.py', '../2026-11-14_OCCOR-01/analyze_occor.py', '../2026-11-14_OCGEO-01/analyze_ocgeo.py',
       '../2026-11-14_OCGEO-01/analyze_ocgeo_test.py']
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()   # noqa: E731


def templates():
    return sorted(os.path.relpath(p, HERE) for p in glob.glob(os.path.join(HERE, 'jobs', '*.sh')))


def main():
    files = OWN + templates()
    cur = {f: sha(os.path.join(HERE, f)) for f in files}
    path = os.path.join(HERE, 'prereg_hashes.json')
    if '--verify' in sys.argv:
        reg = json.load(open(path))['files']
        bad = [f for f in reg if cur.get(f) != reg[f]] + [f for f in cur if f not in reg]
        if '--jobs' in sys.argv:
            for t in [f for f in reg if f.startswith('jobs/')]:
                copy = os.path.join(ROOT, 'gha_par', os.path.basename(t))
                if os.path.isfile(copy) and sha(copy) != reg[t]:
                    bad.append(f'{os.path.relpath(copy, ROOT)} не совпадает с шаблоном {t}')
        print('сверка хешей:', 'расхождения ' + str(bad) if bad else f'совпало ({len(reg)} файлов)')
        sys.exit(1 if bad else 0)
    json.dump({'files': cur}, open(path, 'w'), ensure_ascii=False, indent=1)
    print('записано', len(cur))


if __name__ == '__main__':
    main()
