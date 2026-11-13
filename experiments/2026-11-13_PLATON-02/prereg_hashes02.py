#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-02: sha256 файлов на момент регистрации → prereg_hashes02.json; --verify — сверка. Общий код PLATON-01 сверяется с его
регистрацией; зёрна теста не должны пересекаться с пилотом этого опыта."""
import hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); P1 = os.path.join(HERE, '..', '2026-11-12_PLATON-01')
SHARED = ['platon_world.py', 'platon_check.py', 'platon_jobs.py', 'platon_analyze.py']
OWN = ['platon02_world.py', 'platon02_run.py', 'test_platon02.py', 'dry_platon02.py', 'run_platon02.sh', 'prereg_hashes02.py',
       'cfg_platon02_haiku.json', 'seeds_test.json', 'power02.py', 'power02.json']
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()


def check():
    reg1 = json.load(open(os.path.join(P1, 'prereg_hashes.json'), encoding='utf-8'))['files']
    ok = all(sha(os.path.join(P1, f)) == reg1[f] for f in SHARED) and sha(os.path.join(HERE, '../../tools/run_sealed2.py')) == reg1['../../tools/run_sealed2.py']
    test = {e['seed'] for e in json.load(open(os.path.join(HERE, 'seeds_test.json')))}
    pil = {e['seed'] for e in json.load(open(os.path.join(HERE, 'pilot', 'seeds_pilot_all.json')))}
    print('общий код совпадает с регистрацией PLATON-01:', ok, '| пересечение зёрен теста и пилота:', sorted(test & pil) or 'нет')
    return ok and not (test & pil)


def main():
    if not check():
        sys.exit(1)
    cur = {**{f'../2026-11-12_PLATON-01/{f}': sha(os.path.join(P1, f)) for f in SHARED}, **{f: sha(os.path.join(HERE, f)) for f in OWN}}
    path = os.path.join(HERE, 'prereg_hashes02.json')
    if '--verify' in sys.argv:
        reg = json.load(open(path))['files']; bad = [f for f in cur if reg.get(f) != cur[f]]
        print('сверка хешей:', 'расхождения ' + str(bad) if bad else 'совпало'); sys.exit(1 if bad else 0)
    json.dump({'files': cur}, open(path, 'w'), ensure_ascii=False, indent=1); print('записано', len(cur))


if __name__ == '__main__':
    main()
