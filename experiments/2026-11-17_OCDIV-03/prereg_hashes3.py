#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-03: sha256 файлов на момент регистрации → prereg_hashes3.json; --verify [--jobs] — сверка перед счётом.
В списке:
- код опыта, HYPOTHESIS.md, ожидания;
- код OCDIV-02, которым идут извлечение и счёт Т4 (без изменений), и цепочка зарегистрированного кода, на который он опирается
  (OCDIV-01 → OCPOST-01 → OCSHIFT-01, OCINT-01 → OCREP-01 → OCMIX-01 → OCCOR-01 → OCGEO-01), distill.py (DISTILL-01);
- замок сырого вывода (tools/raw_status.py и его тест), файл workflow;
- вывод пилота 2 «тысяч» (ответы голов — из них анализ теста заново учит модели), разборы пилота OCDIV-02 и OCDIV-03;
- стенограмма совета по трём линзам и шаблоны заданий (jobs/).
С --jobs копии шаблонов в gha_par/ (если они там есть) должны побайтно совпасть со своими шаблонами."""
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OWN = ['ocdiv3.py', 'test_ocdiv3.py', 'make_jobs3.py', 'prereg_hashes3.py', 'HYPOTHESIS.md', 'expect_ocdiv3.json',
       '../2026-11-17_OCDIV-02/ocdiv2.py', '../2026-11-17_OCDIV-02/ocdiv2_extract.py', '../2026-11-17_OCDIV-02/trunc_check.py',
       '../2026-11-17_OCDIV-02/prereg_hashes2.json', '../2026-11-17_DISTILL-01/distill.py',
       '../../.github/workflows/neu-par.yml', '../../tools/raw_status.py', '../../tools/test_raw_status.py',
       '../../gha_out/ocdiv2_sum_pilot2v2/pilot.json', '../../gha_out/ocdiv3_pilot/pilot.json',
       '../2026-11-16_OCDIV-01/ocdiv.py', '../2026-11-16_OCDIV-01/ocdiv_extract.py',
       '../2026-11-15_OCPOST-01/ocpost.py', '../2026-11-15_OCPOST-01/ocpost_extract.py',
       '../2026-11-15_OCSHIFT-01/analyze_ocshift.py', '../2026-11-15_OCSHIFT-01/analyze_ocshift_test.py', '../2026-11-15_OCSHIFT-01/ocshift_extract.py',
       '../2026-11-15_OCINT-01/ocint.py', '../2026-11-15_OCREP-01/analyze_ocrep.py', '../2026-11-15_OCREP-01/analyze_ocrep_test.py',
       '../2026-11-14_OCMIX-01/analyze_ocmix.py', '../2026-11-14_OCCOR-01/analyze_occor.py', '../2026-11-14_OCGEO-01/analyze_ocgeo.py',
       '../2026-11-14_OCGEO-01/analyze_ocgeo_test.py']
PILOT2 = glob.glob(os.path.join(ROOT, 'gha_out/ocdiv2_pilot2_*_T/answers_*.json'))
COUNCIL = glob.glob(os.path.join(ROOT, 'docs/council/2026-11-17_OCDIV-03-lenses_session*.json'))
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()   # noqa: E731


def templates():
    return sorted(os.path.relpath(p, HERE) for p in glob.glob(os.path.join(HERE, 'jobs', '*.sh')))


def main():
    files = OWN + sorted(os.path.relpath(p, HERE) for p in PILOT2 + COUNCIL) + templates()
    cur = {f: sha(os.path.join(HERE, f)) for f in files}
    path = os.path.join(HERE, 'prereg_hashes3.json')
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
    json.dump({'files': cur}, open(path, 'w'), ensure_ascii=False, indent=1)
    print('записано', len(cur))


if __name__ == '__main__':
    main()
