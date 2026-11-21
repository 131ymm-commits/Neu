#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCINT-01: sha256 файлов на момент регистрации → prereg_hashes.json; --verify — сверка перед счётом.
В списке — код опыта, зарегистрированный код OCSHIFT-01 и прежних опытов, на который он опирается, сценарии заданий
(шаблоны и их копии в gha_jobs), файл workflow и данные настоящих сред."""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OWN = ['ocint.py', 'test_ocint.py', 'prereg_hashes.py', 'expect_ocint.py', 'gha_job_ocint_worlds.sh', 'gha_job_ocint_real.sh',
       '../../gha_jobs/ocint_worlds.sh', '../../gha_jobs/ocint_real.sh', '../../.github/workflows/neu-run.yml',
       '../2026-11-15_OCSHIFT-01/analyze_ocshift.py', '../2026-11-15_OCSHIFT-01/analyze_ocshift_test.py', '../2026-11-15_OCSHIFT-01/dry_ocshift.py',
       '../2026-11-15_OCSHIFT-01/ocshift_extract.py', '../2026-11-15_OCREP-01/analyze_ocrep.py', '../2026-11-15_OCREP-01/analyze_ocrep_test.py',
       '../2026-11-14_OCMIX-01/analyze_ocmix.py', '../2026-11-14_OCCOR-01/analyze_occor.py', '../2026-11-14_OCGEO-01/analyze_ocgeo.py',
       '../2026-11-14_OCGEO-01/analyze_ocgeo_test.py',
       '../2026-11-15_OCSHIFT-01/run/out/answers.json', '../2026-11-14_OCCOR-01/run/out/answers.json', '../2026-11-14_OCMIX-01/run/out/answers.json',
       '../2026-11-15_OCREP-01/run/out/answers.json', '../2026-11-15_OCREP-01/pilot/out/answers.json']
PAIRS = [('gha_job_ocint_worlds.sh', '../../gha_jobs/ocint_worlds.sh'), ('gha_job_ocint_real.sh', '../../gha_jobs/ocint_real.sh')]
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()   # noqa: E731


def main():
    cur = {f: sha(os.path.join(HERE, f)) for f in OWN}
    path = os.path.join(HERE, 'prereg_hashes.json')
    bad = [f'{b} не совпадает с шаблоном {a}' for a, b in PAIRS if cur[a] != cur[b]]
    if '--verify' in sys.argv:
        reg = json.load(open(path))['files']
        bad += [f for f in cur if reg.get(f) != cur[f]]
        print('сверка хешей:', 'расхождения ' + str(bad) if bad else 'совпало')
        sys.exit(1 if bad else 0)
    if bad:
        print('копии заданий не совпадают с шаблонами:', bad)
        sys.exit(1)
    json.dump({'files': cur}, open(path, 'w'), ensure_ascii=False, indent=1)
    print('записано', len(cur))


if __name__ == '__main__':
    main()
