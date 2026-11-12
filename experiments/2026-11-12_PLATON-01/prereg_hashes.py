#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-01: sha256 кода, зёрен, конфигурации и промптов на момент регистрации → prereg_hashes.json.

  python3 prereg_hashes.py            — записать prereg_hashes.json (только до регистрации)
  python3 prereg_hashes.py --verify   — сверить текущие файлы с prereg_hashes.json; код 1 при расхождении
Промпты теста: sha256 каждого промпта по id таблицы (из run/prompts.sha256 после build) сверяются отдельно в run_platon.sh.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ['platon_world.py', 'platon_check.py', 'platon_jobs.py', 'platon_analyze.py', 'test_platon.py', 'dry_platon.py',
         'power_platon.py', 'prereg_hashes.py', 'run_platon.sh', 'cfg_platon_haiku.json', 'seeds_test.json',
         '../../tools/run_sealed2.py']


def sha(p):
    with open(os.path.join(HERE, p), 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    path = os.path.join(HERE, 'prereg_hashes.json')
    cur = {f: sha(f) for f in FILES}
    if '--verify' in sys.argv:
        reg = json.load(open(path, encoding='utf-8'))['files']
        bad = [f for f in FILES if reg.get(f) != cur[f]]
        for f in bad:
            print(f'✗ {f}: sha256 не совпал с регистрацией')
        print('сверка хешей:', 'расхождения' if bad else 'совпало')
        sys.exit(1 if bad else 0)
    json.dump({'files': cur}, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({'files': cur}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
