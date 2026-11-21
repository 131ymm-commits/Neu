#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-02: sha256 файлов на момент регистрации → prereg_hashes_d2.json; --verify [--jobs] — сверка перед счётом теста (задание анализа
останавливается при расхождении). В списке:
- код опыта, HYPOTHESIS.md, ожидания и скрипты, которые печатают числа PREREG; сухой прогон (dry_d2.py); каркас отчёта (report_d2.py,
  check_report_d2.py — написаны до вывода анализа);
- код OCDIV-04 и его хеши (цепочка OCDIV-03 → OCDIV-02 → OCDIV-01 и ранее — в prereg_hashes4.json), код OCDIV-02, который строит среды
  и прогоняет головы (ocdiv2_extract.py), ocpost_extract.py (задачи и range), сборка OCDIV-03/04;
- замок сырого вывода (tools/raw_status.py и его тест), файл workflow;
- ответы построения (тест OCDIV-03, пилот и тест OCDIV-04 — answers_*.json), вывод пилотов DISTILL-02 (1, 2, 3) и сухого прогона;
- стенограмма совета 74; шаблоны 109 заданий (jobs/) и шаблоны пилотов.
С --jobs копии шаблонов в gha_par/ (если они там есть) должны побайтно совпасть со своими шаблонами.
  python3 prereg_hashes_d2.py [--verify [--jobs]]"""
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OWN = ['distill02.py', 'distill02_extract.py', 'test_distill02.py', 'make_jobs_d2.py', 'prereg_hashes_d2.py', 'dry_d2.py', 'HYPOTHESIS.md',
       'report_d2.py', 'check_report_d2.py',
       'expect_d2.json', 'prereg_expect_d2.py', 'prereg_power_d2.py', 'prereg_power_d2.json', 'prereg_tables_d2.py', 'prereg_derived_d2.py',
       'prereg_derived_d2.json',
       '../2026-11-18_OCDIV-04/ocdiv4.py', '../2026-11-18_OCDIV-04/ocdiv4_extract.py', '../2026-11-18_OCDIV-04/prereg_hashes4.json',
       '../2026-11-17_OCDIV-03/ocdiv3.py', '../2026-11-17_OCDIV-02/ocdiv2.py', '../2026-11-17_OCDIV-02/ocdiv2_extract.py',
       '../2026-11-17_OCDIV-02/trunc_check.py', '../2026-11-15_OCPOST-01/ocpost_extract.py', '../2026-11-16_OCDIV-01/ocdiv_extract.py',
       '../2026-11-16_OCDIV-01/ocdiv.py', '../2026-11-15_OCSHIFT-01/analyze_ocshift.py',
       '../../.github/workflows/neu-par.yml', '../../tools/raw_status.py', '../../tools/test_raw_status.py',
       '../../gha_out/distill02_pilot/pilot.json', '../../gha_out/distill02_pilot2/pilot2.json', '../../gha_out/distill02_pilot3/pilot3.json',
       '../../gha_out/distill02_dry/dry_summary.txt', '../../docs/council/2026-11-18_DISTILL-02-lenses_session74.json']
ANSWERS = (glob.glob(os.path.join(ROOT, 'gha_out/ocdiv3_test_*/answers_*.json')) + glob.glob(os.path.join(ROOT, 'gha_out/ocdiv4_pilot_*/answers_*.json'))
           + glob.glob(os.path.join(ROOT, 'gha_out/ocdiv4_test_*/answers_*.json')))
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()   # noqa: E731


def templates():
    return sorted(os.path.relpath(p, HERE) for p in glob.glob(os.path.join(HERE, 'jobs', '*.sh')))


def main():
    files = OWN + sorted(os.path.relpath(p, HERE) for p in ANSWERS) + templates()
    cur = {f: sha(os.path.join(HERE, f)) for f in files}
    path = os.path.join(HERE, 'prereg_hashes_d2.json')
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
    n_jobs = sum(1 for f in cur if f.startswith('jobs/distill02_test_') or f.startswith('jobs/distill02_rep_') or f == 'jobs/distill02_sum_test.sh')
    json.dump({'files': cur, 'n_job_templates_test': n_jobs}, open(path, 'w'), ensure_ascii=False, indent=1)
    print('записано', len(cur), '| шаблонов теста (108 заданий и анализ):', n_jobs)


if __name__ == '__main__':
    main()
