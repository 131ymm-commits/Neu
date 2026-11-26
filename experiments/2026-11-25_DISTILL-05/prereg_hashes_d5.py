#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-05: sha256 файлов на момент регистрации → prereg_hashes_d5.json; --verify [--jobs] — сверка в задании анализа (при
расхождении задание останавливается). В списке: код и тексты опыта; все шаблоны jobs/; вывод разведки, проверок кода и пилота и их задания
в gha_par/; код, на который опирается опыт (DISTILL-04: сборка, классификация, сверка повторов; DISTILL-02; OCDIV-01/02/04), и
prereg_hashes_d4.json (через него — цепочка регистраций DISTILL-04 → … → OCDIV-01, замок сырого вывода, neu-par.yml); стенограмма и
задание совета 80. С --jobs копия шаблона в gha_par/ (если она там есть) должна побайтно совпасть с шаблоном.
  python3 prereg_hashes_d5.py [--verify [--jobs]]"""
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CODE = ['explore_d5.py', 'test_explore_d5.py', 'distill05_extract.py', 'scales_d5.py', 'test_scales_d5.py', 'make_jobs_d5.py',
        'prereg_numbers_d5.py', 'prereg_hashes_d5.py']
TEXT = ['HYPOTHESIS.md', 'NOTE-explore.md', 'PREREG-DISTILL-05.md', 'expect_d5.json', 'prereg_numbers_d5.log']
OUTS = ['../../gha_out/distill05_explore/explore.json', '../../gha_out/distill05_pilot/pilot.json', '../../gha_out/distill05_check/tests.log',
        '../../gha_out/distill05_check2/tests.log'] + [f'../../gha_par/distill05_{j}.sh' for j in ('check', 'check2', 'explore', 'pilot')]
DEPS = ['../2026-11-19_DISTILL-04/distill04_extract.py', '../2026-11-19_DISTILL-04/explore_d4.py', '../2026-11-19_DISTILL-04/rep_check_d4.py',
        '../2026-11-19_DISTILL-04/prereg_hashes_d4.json', '../2026-11-18_DISTILL-02/distill02.py', '../2026-11-17_OCDIV-02/ocdiv2_extract.py',
        '../2026-11-17_OCDIV-02/ocdiv2.py', '../2026-11-18_OCDIV-04/ocdiv4.py', '../2026-11-16_OCDIV-01/ocdiv.py', '../../tools/raw_status.py',
        '../../tools/test_raw_status.py', '../../.github/workflows/neu-par.yml']
COUNCIL = ['../../docs/council/2026-11-26_DISTILL-05-lenses_session80_task.md', '../../docs/council/2026-11-26_DISTILL-05-lenses_session80.json']
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()   # noqa: E731


def templates():
    return sorted(os.path.relpath(p, HERE) for p in glob.glob(os.path.join(HERE, 'jobs', '*.sh')))


def main():
    files = sorted(set(CODE + TEXT + OUTS + DEPS + COUNCIL + templates()))
    path = os.path.join(HERE, 'prereg_hashes_d5.json')
    if '--verify' in sys.argv:
        reg = json.load(open(path))['files']
        cur = {f: sha(os.path.join(HERE, f)) for f in set(reg) | set(files) if os.path.isfile(os.path.join(HERE, f))}
        bad = [f for f in reg if cur.get(f) != reg[f]] + [f for f in cur if f not in reg]
        if '--jobs' in sys.argv:
            for t in [f for f in reg if f.startswith('jobs/')]:
                copy = os.path.join(ROOT, 'gha_par', os.path.basename(t))
                if os.path.isfile(copy) and sha(copy) != reg[t]:
                    bad.append(f'{os.path.relpath(copy, ROOT)} не совпадает с шаблоном {t}')
        print('сверка хешей:', 'расхождения ' + str(bad) if bad else f'совпало ({len(reg)} файлов)')
        sys.exit(1 if bad else 0)
    miss = [f for f in files if not os.path.isfile(os.path.join(HERE, f))]
    if miss:
        raise SystemExit(f'СТОП: нет файлов регистрации: {miss}')
    json.dump({'files': {f: sha(os.path.join(HERE, f)) for f in files}, 'n_templates': len(templates())}, open(path, 'w'), ensure_ascii=False, indent=1)
    print('записано', len(files), '| шаблонов заданий:', len(templates()))


if __name__ == '__main__':
    main()
