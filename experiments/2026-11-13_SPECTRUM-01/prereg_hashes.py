#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-01: sha256 файлов на момент регистрации → prereg_hashes.json; --verify — сверка.
Импортируемый код SELF-01/02 сверяется и с регистрацией SELF-02 (его prereg_hashes.json)."""
import hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
S2 = os.path.join(HERE, '..', '2026-10-28_SELF-02')
OWN = ['spectrum01.py', 'analyze_spectrum01.py', 'test_spectrum01.py', 'dry_spectrum01.py', 'power_spectrum01.py', 'power.json',
       'requirements.txt', 'prereg_hashes.py']
SHARED = {'../2026-10-28_SELF-02/exp_self_02.py': os.path.join(S2, 'exp_self_02.py'),
          '../2026-10-27_SELF-01/exp_self_01.py': os.path.join(HERE, '..', '2026-10-27_SELF-01', 'exp_self_01.py')}
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()


def self02_ok():
    reg = json.load(open(os.path.join(S2, 'prereg_hashes.json'), encoding='utf-8'))
    files = reg.get('files', reg)
    hits = {k: v for k, v in files.items() if k.endswith('exp_self_02.py') or k.endswith('exp_self_01.py')}
    ok = all(sha(SHARED['../2026-10-28_SELF-02/exp_self_02.py' if k.endswith('exp_self_02.py') else '../2026-10-27_SELF-01/exp_self_01.py']) == v
             for k, v in hits.items())
    print('код SELF-01/02 совпадает с регистрацией SELF-02:', ok, '| сверено файлов:', len(hits))
    return ok and len(hits) >= 1


def main():
    if not self02_ok():
        sys.exit(1)
    cur = {**{k: sha(p) for k, p in SHARED.items()}, **{f: sha(os.path.join(HERE, f)) for f in OWN}}
    path = os.path.join(HERE, 'prereg_hashes.json')
    if '--verify' in sys.argv:
        reg = json.load(open(path))['files']
        bad = [f for f in cur if reg.get(f) != cur[f]]
        print('сверка хешей:', 'расхождения ' + str(bad) if bad else 'совпало'); sys.exit(1 if bad else 0)
    json.dump({'files': cur}, open(path, 'w'), ensure_ascii=False, indent=1)
    print('записано', len(cur))


if __name__ == '__main__':
    main()
