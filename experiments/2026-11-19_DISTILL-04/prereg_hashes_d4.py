#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04: sha256 файлов на момент регистрации → prereg_hashes_d4.json; --verify [--jobs] — сверка в задании анализа (при
расхождении задание останавливается). В списке:
- код опыта (программа-М, разведка, извлечение, анализ, тесты, сверка повторов, печать чисел PREREG), HYPOTHESIS.md, NOTE-explore.md,
  PREREG, ожидания, все шаблоны заданий (jobs/: 63 задания извлечения, 3 повтора, анализ, разведка и пилоты);
- весь список регистрации DISTILL-03 (prereg_hashes_d3.OWN: ab.py и его тесты, вывод пилотов, стенограмма совета 76) и сам
  prereg_hashes_d3.json; через него — список регистрации DISTILL-02 (код DISTILL-02 и цепочка OCDIV-04 → … → OCDIV-01, замок сырого
  вывода, neu-par.yml);
- ответы построения (тест OCDIV-03, пилот и тест OCDIV-04) и ответы test5/new5 DISTILL-02 (answers_*.json) — данные пилота;
- вывод разведки и пилотов DISTILL-04 и их задания в gha_par/; стенограмма и задание совета 78 (три линзы).
С --jobs копия шаблона в gha_par/ (если она там есть) должна побайтно совпасть с шаблоном.
  python3 prereg_hashes_d4.py [--verify [--jobs]]"""
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
D3_DIR = os.path.join(ROOT, 'experiments', '2026-11-19_DISTILL-03')
sys.path.insert(0, D3_DIR)
import prereg_hashes_d3 as H3  # noqa: E402

CODE = ['prog_m.py', 'explore_d4.py', 'tokenizers_d4.py', 'note_explore_d4.py', 'distill04_extract.py', 'make_jobs_d4.py', 'pilot_d4.py',
        'test_d4.py', 'rep_check_d4.py', 'test_prog_m.py', 'test_explore_d4.py', 'test_extract_d4.py', 'test_analysis_d4.py',
        'prereg_numbers_d4.py', 'prereg_hashes_d4.py', 'null_d4.py', 'null_sum_d4.py', 'norm_bound_d4.py']
TEXT = ['HYPOTHESIS.md', 'NOTE-explore.md', 'PREREG-DISTILL-04.md', 'expect_d4.json', 'prereg_numbers_d4.log', 'norm_bound_d4.json',
        'null_timing_d4.json', 'null_timing_d4.log', 'null_sum_d4.json']
OUTS = ['../../gha_out/distill04_check/tests.log', '../../gha_out/distill04_explore/explore.json', '../../gha_out/distill04_explore/tokenizers.json',
        '../../gha_out/distill04_explore2/explore.json', '../../gha_out/distill04_explore2/tokenizers.json',
        '../../gha_out/distill04_pilot/pilot.json', '../../gha_out/distill04_pilot2/pilot.json',
        '../../gha_par/distill04_check.sh', '../../gha_par/distill04_explore.sh', '../../gha_par/distill04_explore2.sh',
        '../../gha_par/distill04_pilot.sh', '../../gha_par/distill04_pilot2.sh', '../../gha_out/distill04_pilot3/pilot.json',
        '../../gha_par/distill04_pilot3.sh'] + [f'../../gha_out/distill04_null_{k}/null.json' for k in range(1, 5)] + \
       [f'../../gha_par/distill04_null_{k}.sh' for k in range(1, 5)]
COUNCIL = ['../../docs/council/2026-11-19_DISTILL-04-lenses_session78_task.md', '../../docs/council/2026-11-19_DISTILL-04-lenses_session78.json',
           '../../docs/council/2026-11-19_DISTILL-04-lenses_session78.md']
OWN = CODE + TEXT + OUTS + COUNCIL
FROM_D3 = sorted(set(os.path.relpath(os.path.join(D3_DIR, f), HERE) for f in H3.OWN + H3.FROM_D2 + ['prereg_hashes_d3.json']))
ANSWERS = sorted(set(os.path.relpath(os.path.join(D3_DIR, f), HERE) for f in H3.ANSWERS))
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()   # noqa: E731


def templates():
    return sorted(os.path.relpath(p, HERE) for p in glob.glob(os.path.join(HERE, 'jobs', '*.sh')))


def main():
    files = sorted(set(OWN + FROM_D3 + ANSWERS + templates()))
    path = os.path.join(HERE, 'prereg_hashes_d4.json')
    if '--verify' in sys.argv:
        reg = json.load(open(path))['files']
        cur = {f: sha(os.path.join(HERE, f)) for f in reg if os.path.isfile(os.path.join(HERE, f))}
        cur.update({f: sha(os.path.join(HERE, f)) for f in files if f not in cur})
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
    cur = {f: sha(os.path.join(HERE, f)) for f in files}
    n_t = len(templates())
    json.dump({'files': cur, 'n_answers': len(ANSWERS), 'n_templates': n_t}, open(path, 'w'), ensure_ascii=False, indent=1)
    print('записано', len(cur), '| ответов (построение и test5/new5 DISTILL-02):', len(ANSWERS), '| шаблонов заданий:', n_t)


if __name__ == '__main__':
    main()
