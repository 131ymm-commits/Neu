#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCCOR-01: sha256 файлов на момент регистрации → prereg_hashes.json; --verify — сверка перед прогоном и анализом.
Анализ OCCOR-01 берёт калибровку, выбор и ИОИ из зарегистрированного кода OCGEO-01 — его файлы тоже в списке."""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OWN = ['occor_extract_test.py', 'occor_extract.py', 'analyze_occor.py', 'analyze_occor_test.py', 'pilot_occor.py', 'power_occor.py',
       'power.json', 'test_occor.py', 'dry_occor.py', 'prereg_hashes.py',
       '../2026-11-14_OCGEO-01/analyze_ocgeo.py', '../2026-11-14_OCGEO-01/analyze_ocgeo_test.py']
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
