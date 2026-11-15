#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCSHIFT-01: sha256 файлов на момент регистрации → prereg_hashes.json; --verify — сверка перед прогоном и анализом.
Анализ берёт оценщики и счёт из зарегистрированного кода OCREP-01, OCMIX-01, OCCOR-01 и OCGEO-01 — их файлы тоже в списке."""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OWN = ['ocshift_extract_test.py', 'ocshift_extract.py', 'analyze_ocshift.py', 'analyze_ocshift_test.py', 'pilot_ocshift.py', 'power_ocshift.py',
       'test_ocshift.py', 'dry_ocshift.py', 'explore_shifts.py', 'gha_ocshift_test.sh', 'prereg_hashes.py',
       '../../gha_out/ocshift_chain/power.json', '../../gha_out/ocshift_pilot/analysis_pilot.json',
       '../2026-11-15_OCREP-01/analyze_ocrep.py', '../2026-11-15_OCREP-01/analyze_ocrep_test.py', '../2026-11-15_OCREP-01/pilot/out/answers.json',
       '../2026-11-14_OCMIX-01/analyze_ocmix.py', '../2026-11-14_OCCOR-01/analyze_occor.py', '../2026-11-14_OCGEO-01/analyze_ocgeo.py',
       '../2026-11-14_OCGEO-01/analyze_ocgeo_test.py']
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()   # noqa: E731


def main():
    cur = {f: sha(os.path.join(HERE, f)) for f in OWN}
    path = os.path.join(HERE, 'prereg_hashes.json')
    if '--verify' in sys.argv:
        reg = json.load(open(path))['files']
        bad = [f for f in cur if reg.get(f) != cur[f]]
        print('сверка хешей:', 'расхождения ' + str(bad) if bad else 'совпало')
        sys.exit(1 if bad else 0)
    json.dump({'files': cur}, open(path, 'w'), ensure_ascii=False, indent=1)
    print('записано', len(cur))


if __name__ == '__main__':
    main()
