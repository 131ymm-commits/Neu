#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-01R: sha256 файлов на момент регистрации → prereg_hashes_r.json; --verify — сверка.
Проверяет также, что общий код мира, разбора и анализа совпадает с регистрацией PLATON-01 (тот же код байт в байт),
и что зёрна теста не пересекаются ни с какими прежними зёрнами PLATON-01 и пилотами повтора."""
import hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.join(HERE, '..', '2026-11-12_PLATON-01')
SHARED = ['platon_world.py', 'platon_check.py', 'platon_jobs.py', 'platon_analyze.py']
OWN = ['run_platon_r.sh', 'prereg_hashes_r.py', 'power_r.py', 'cfg_platon_sonnet.json', 'seeds_test_r.json']
TOOLS = ['../../tools/run_sealed2.py']


def sha(p):
    with open(p, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def seeds(path):
    return {e['seed'] for e in json.load(open(path, encoding='utf-8'))}


def check():
    ok = True
    reg1 = json.load(open(os.path.join(P1, 'prereg_hashes.json'), encoding='utf-8'))['files']
    for f in SHARED:
        if sha(os.path.join(P1, f)) != reg1[f]:
            print(f'✗ {f}: код PLATON-01 изменён после его регистрации'); ok = False
    if sha(os.path.join(HERE, TOOLS[0])) != reg1['../../tools/run_sealed2.py']:
        print('✗ tools/run_sealed2.py изменён после регистрации PLATON-01'); ok = False
    test = seeds(os.path.join(HERE, 'seeds_test_r.json'))
    used = set(range(70000, 71000)) | set(range(75000, 76000))
    used |= seeds(os.path.join(P1, 'seeds_test.json')) | seeds(os.path.join(P1, 'dry', 'seeds_dry.json'))
    for d in (os.path.join(P1, 'pilot'), os.path.join(HERE, 'pilot')):
        for f in os.listdir(d):
            if f.startswith('seeds_') and f.endswith('.json'):
                used |= seeds(os.path.join(d, f))
    bad = sorted(test & used)
    print(f'зёрна теста R: {min(test)}–{max(test)} ({len(test)}); пересечений с прежними: {bad or "нет"}')
    return ok and not bad


def main():
    path = os.path.join(HERE, 'prereg_hashes_r.json')
    if not check():
        sys.exit(1)
    cur = {**{f'../2026-11-12_PLATON-01/{f}': sha(os.path.join(P1, f)) for f in SHARED},
           **{f: sha(os.path.join(HERE, f)) for f in OWN}, TOOLS[0]: sha(os.path.join(HERE, TOOLS[0]))}
    if '--verify' in sys.argv:
        reg = json.load(open(path, encoding='utf-8'))['files']
        bad = [f for f in cur if reg.get(f) != cur[f]]
        for f in bad:
            print(f'✗ {f}: sha256 не совпал с регистрацией')
        print('сверка хешей:', 'расхождения' if bad else 'совпало')
        sys.exit(1 if bad else 0)
    json.dump({'files': cur}, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('записано', len(cur), 'файлов')


if __name__ == '__main__':
    main()
