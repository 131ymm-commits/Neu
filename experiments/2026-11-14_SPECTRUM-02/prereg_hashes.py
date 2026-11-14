#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-02: sha256 файлов на момент регистрации → prereg_hashes.json; --verify — сверка (запускается перед прогоном,
в том числе на GitHub Actions). Импортируемый код SPECTRUM-01 сверяется и с регистрацией SPECTRUM-01, код SELF-01/02 —
с регистрацией SELF-02."""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
S01 = os.path.join(HERE, '..', '2026-11-13_SPECTRUM-01')
OWN = ['spectrum02.py', 'analyze_spectrum02.py', 'test_spectrum02.py', 'dry_spectrum02.py', 'power_spectrum02.py', 'power.json',
       'requirements.txt', 'prereg_hashes.py', 'gha_spectrum02.sh']
SHARED = {'../2026-11-13_SPECTRUM-01/spectrum01.py': os.path.join(S01, 'spectrum01.py'),
          '../2026-11-13_SPECTRUM-01/analyze_spectrum01.py': os.path.join(S01, 'analyze_spectrum01.py'),
          '../2026-10-28_SELF-02/exp_self_02.py': os.path.join(HERE, '..', '2026-10-28_SELF-02', 'exp_self_02.py'),
          '../2026-10-27_SELF-01/exp_self_01.py': os.path.join(HERE, '..', '2026-10-27_SELF-01', 'exp_self_01.py')}
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()   # noqa: E731


def spectrum01_ok():
    reg = json.load(open(os.path.join(S01, 'prereg_hashes.json'), encoding='utf-8'))['files']
    pairs = {'spectrum01.py': SHARED['../2026-11-13_SPECTRUM-01/spectrum01.py'],
             'analyze_spectrum01.py': SHARED['../2026-11-13_SPECTRUM-01/analyze_spectrum01.py'],
             '../2026-10-28_SELF-02/exp_self_02.py': SHARED['../2026-10-28_SELF-02/exp_self_02.py'],
             '../2026-10-27_SELF-01/exp_self_01.py': SHARED['../2026-10-27_SELF-01/exp_self_01.py']}
    bad = [k for k, p in pairs.items() if reg.get(k) != sha(p)]
    print('код SPECTRUM-01 и SELF-01/02 совпадает с регистрацией SPECTRUM-01:', not bad, '| расхождения:', bad)
    return not bad


def main():
    if not spectrum01_ok():
        sys.exit(1)
    cur = {**{k: sha(p) for k, p in SHARED.items()}, **{f: sha(os.path.join(HERE, f)) for f in OWN}}
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
