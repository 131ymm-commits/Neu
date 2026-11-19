#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-03: sha256 файлов на момент регистрации → prereg_hashes_d3.json; --verify [--jobs] — сверка перед счётом теста (задание теста
останавливается при расхождении). В списке:
- код опыта (ab.py, тесты, мощность, печать чисел PREREG), HYPOTHESIS.md, PREREG, ожидания, шаблон задания теста (jobs/);
- весь список регистрации DISTILL-02 (prereg_hashes_d2.OWN: код DISTILL-02 и цепочка OCDIV-04 → … → OCDIV-01, замок сырого вывода,
  neu-par.yml) и сам prereg_hashes_d2.json; ответы построения (тест OCDIV-03, пилот и тест OCDIV-04) и ответы теста DISTILL-02
  (test5 и new5 — answers_*.json), analysis.json DISTILL-02 (формулы для сверки программ);
- вывод пилотов DISTILL-03 (вторая попытка 64086bcb и пилот новым кодом с мощностью), стенограмма совета 76.
С --jobs копия шаблона в gha_par/ (если она там есть) должна побайтно совпасть с шаблоном.
  python3 prereg_hashes_d3.py [--verify [--jobs]]"""
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
D2_DIR = os.path.join(ROOT, 'experiments', '2026-11-18_DISTILL-02')
sys.path.insert(0, D2_DIR)
import prereg_hashes_d2 as H2  # noqa: E402

OWN = ['ab.py', 'test_ab.py', 'power_ab.py', 'prereg_hashes_d3.py', 'prereg_numbers_d3.py', 'HYPOTHESIS.md', 'PREREG-DISTILL-03.md',
       'expect_d3.json', '../../gha_out/distill03_pilot/pilot.json', '../../gha_out/distill03_pilot/fits.json',
       '../../gha_out/distill03_power/pilot.json', '../../gha_out/distill03_power/power.json',
       '../../gha_out/distill02_sum_test/analysis.json', '../../docs/council/2026-11-19_DISTILL-03-lenses_session76.json']
FROM_D2 = sorted(set(os.path.relpath(os.path.join(D2_DIR, f), HERE) for f in H2.OWN + ['prereg_hashes_d2.json']))
ANSWERS = sorted(os.path.relpath(p, HERE) for p in H2.ANSWERS + glob.glob(os.path.join(ROOT, 'gha_out/distill02_test_*/answers_*.json')))
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()   # noqa: E731


def templates():
    return sorted(os.path.relpath(p, HERE) for p in glob.glob(os.path.join(HERE, 'jobs', '*.sh')))


def main():
    files = OWN + FROM_D2 + ANSWERS + templates()
    cur = {f: sha(os.path.join(HERE, f)) for f in files}
    path = os.path.join(HERE, 'prereg_hashes_d3.json')
    if '--verify' in sys.argv:
        reg = json.load(open(path))['files']
        bad = [f for f in reg if cur.get(f) != reg[f]] + [f for f in cur if f not in reg]
        if '--jobs' in sys.argv:
            for t in [f for f in reg if f.startswith('jobs/')]:
                copy = os.path.join(ROOT, 'gha_par', os.path.basename(t))
                if os.path.isfile(copy) and sha(copy) != reg[t]:
                    bad.append(f'{os.path.relpath(copy, ROOT)} не совпадает с шаблоном {t}')
        print('сверка хешей:', 'расхождения ' + str(bad) if bad else f'совпало ({len(reg)} файлов)')
        sys.exit(1 if bad else 0)
    n_ans = len(ANSWERS)
    json.dump({'files': cur, 'n_answers': n_ans}, open(path, 'w'), ensure_ascii=False, indent=1)
    print('записано', len(cur), '| ответов (построение и тест DISTILL-02):', n_ans)


if __name__ == '__main__':
    main()
