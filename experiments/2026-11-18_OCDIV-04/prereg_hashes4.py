#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-04: sha256 файлов на момент регистрации → prereg_hashes4.json; --verify [--jobs] — сверка перед счётом теста.
В списке:
- код опыта, HYPOTHESIS.md, ожидания;
- код OCDIV-03 (ocdiv3.py: permute_wrong, mean_entry, t4_stream, пары) и его хеши; код OCDIV-02 (извлечение, сборка, счёт) и цепочка
  зарегистрированного кода, на который он опирается (OCDIV-01 → OCPOST-01 → OCSHIFT-01, OCINT-01 → OCREP-01 → OCMIX-01 → OCCOR-01 →
  OCGEO-01), distill.py (импортирует ocdiv3);
- замок сырого вывода (tools/raw_status.py и его тест), файл workflow;
- вывод пилота OCDIV-04 (ответы голов фазы pilot3) и его разбор; стенограмма совета по трём линзам; шаблоны заданий (jobs/).
С --jobs копии шаблонов в gha_par/ (если они там есть) должны побайтно совпасть со своими шаблонами."""
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OWN = ['ocdiv4.py', 'ocdiv4_extract.py', 'test_ocdiv4.py', 'make_jobs4.py', 'prereg_hashes4.py', 'posthoc_offsets3.py', 'report_ocdiv4.py',
       'HYPOTHESIS.md', 'HYPOTHESIS-ADDENDUM.md', 'expect_ocdiv4.json',
       '../2026-11-17_OCDIV-03/ocdiv3.py', '../2026-11-17_OCDIV-03/prereg_hashes3.json',
       '../2026-11-17_OCDIV-02/ocdiv2.py', '../2026-11-17_OCDIV-02/ocdiv2_extract.py', '../2026-11-17_OCDIV-02/trunc_check.py',
       '../2026-11-17_OCDIV-02/prereg_hashes2.json', '../2026-11-17_DISTILL-01/distill.py',
       '../../.github/workflows/neu-par.yml', '../../tools/raw_status.py', '../../tools/test_raw_status.py',
       '../../gha_out/ocdiv4_sum_pilot/pilot.json', '../../gha_out/ocdiv4_sum_pilot2/pilot.json', '../../gha_out/ocdiv4_sum_pilot3/pilot.json',
       '../2026-11-16_OCDIV-01/ocdiv.py', '../2026-11-16_OCDIV-01/ocdiv_extract.py',
       '../2026-11-15_OCPOST-01/ocpost.py', '../2026-11-15_OCPOST-01/ocpost_extract.py',
       '../2026-11-15_OCSHIFT-01/analyze_ocshift.py', '../2026-11-15_OCSHIFT-01/analyze_ocshift_test.py', '../2026-11-15_OCSHIFT-01/ocshift_extract.py',
       '../2026-11-15_OCINT-01/ocint.py', '../2026-11-15_OCREP-01/analyze_ocrep.py', '../2026-11-15_OCREP-01/analyze_ocrep_test.py',
       '../2026-11-14_OCMIX-01/analyze_ocmix.py', '../2026-11-14_OCCOR-01/analyze_occor.py', '../2026-11-14_OCGEO-01/analyze_ocgeo.py',
       '../2026-11-14_OCGEO-01/analyze_ocgeo_test.py']
PILOT = glob.glob(os.path.join(ROOT, 'gha_out/ocdiv4_pilot_*/answers_*.json'))
COUNCIL = glob.glob(os.path.join(ROOT, 'docs/council/2026-11-18_OCDIV-04-lenses_session*.json'))
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()   # noqa: E731


def templates():
    return sorted(os.path.relpath(p, HERE) for p in glob.glob(os.path.join(HERE, 'jobs', '*.sh')))


def main():
    files = OWN + sorted(os.path.relpath(p, HERE) for p in PILOT + COUNCIL) + templates()
    cur = {f: sha(os.path.join(HERE, f)) for f in files}
    path = os.path.join(HERE, 'prereg_hashes4.json')
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
