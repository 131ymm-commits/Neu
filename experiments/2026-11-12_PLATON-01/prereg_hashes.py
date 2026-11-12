#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-01: sha256 кода, зёрен, конфигурации и промптов на момент регистрации → prereg_hashes.json.

  python3 prereg_hashes.py            — записать prereg_hashes.json (только до регистрации)
  python3 prereg_hashes.py --verify   — сверить текущие файлы с prereg_hashes.json; код 1 при расхождении
Обе команды сначала проверяют, что зёрна теста не пересекаются с пилотами, сухим прогоном и модульными тестами.
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


def check_seeds():
    """Совет 42, правка 1: зёрна теста не пересекаются с пилотами (90001–90031 по файлам pilot/seeds_*.json),
    сухим прогоном (dry/seeds_dry.json) и зёрнами модульных тестов (70000–70999, 75000–75999)."""
    test = {e['seed'] for e in json.load(open(os.path.join(HERE, 'seeds_test.json'), encoding='utf-8'))}
    used = {}
    for f in sorted(os.listdir(os.path.join(HERE, 'pilot'))):
        if f.startswith('seeds_') and f.endswith('.json'):
            used[f'pilot/{f}'] = {e['seed'] for e in json.load(open(os.path.join(HERE, 'pilot', f), encoding='utf-8'))}
    used['dry/seeds_dry.json'] = {e['seed'] for e in json.load(open(os.path.join(HERE, 'dry', 'seeds_dry.json'), encoding='utf-8'))}
    used['модульные тесты'] = set(range(70000, 71000)) | set(range(75000, 76000))
    bad = {k: sorted(test & v) for k, v in used.items() if test & v}
    pilots = sorted(set().union(*[v for k, v in used.items() if k.startswith('pilot/')]))
    print(f'зёрна теста: {min(test)}–{max(test)} ({len(test)}); пилоты: {pilots[0]}–{pilots[-1]} ({len(pilots)}); '
          f'пересечений: {bad or "нет"}')
    return not bad


def main():
    path = os.path.join(HERE, 'prereg_hashes.json')
    if not check_seeds():
        print('✗ зёрна теста пересекаются с уже использованными')
        sys.exit(1)
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
