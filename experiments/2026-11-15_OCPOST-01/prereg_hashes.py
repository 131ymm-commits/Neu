#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCPOST-01: sha256 файлов на момент регистрации → prereg_hashes.json; --verify [--job ИМЯ] — сверка перед счётом.
В списке — код опыта, зарегистрированный код OCSHIFT-01, OCINT-01 и прежних опытов, на который он опирается, шаблоны заданий
GitHub Actions, файл workflow, вывод пилота. При сверке с --job ИМЯ копия gha_jobs/ИМЯ.sh должна побайтно совпасть со своим
шаблоном (как в OCSHIFT-01, совет 60): копия кладётся в gha_jobs только в день запуска, поэтому сверяется лишь запускаемая."""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WRAPPERS = {'ocpost_test': 'gha_job_ocpost_test.sh', 'ocpost_tail_a': 'gha_job_ocpost_tail_a.sh', 'ocpost_tail_b': 'gha_job_ocpost_tail_b.sh',
            'ocpost_tail_sum': 'gha_job_ocpost_tail_sum.sh'}
OWN = ['ocpost_extract.py', 'ocpost.py', 'test_ocpost.py', 'dry_ocpost.py', 'prereg_hashes.py', 'power_ocpost.py', *WRAPPERS.values(),
       '../../.github/workflows/neu-run.yml', '../../gha_jobs/ocpost_pilot.sh',
       '../../gha_out/ocpost_pilot/pilot_envs.json', '../../gha_out/ocpost_pilot/pilot_worlds.json', '../../gha_out/ocpost_pilot/pilot_tail.json',
       '../2026-11-15_OCSHIFT-01/analyze_ocshift.py', '../2026-11-15_OCSHIFT-01/analyze_ocshift_test.py', '../2026-11-15_OCSHIFT-01/dry_ocshift.py',
       '../2026-11-15_OCSHIFT-01/ocshift_extract.py', '../2026-11-15_OCINT-01/ocint.py', '../2026-11-15_OCREP-01/analyze_ocrep.py',
       '../2026-11-15_OCREP-01/analyze_ocrep_test.py', '../2026-11-15_OCREP-01/pilot/out/answers.json',
       '../2026-11-14_OCMIX-01/analyze_ocmix.py', '../2026-11-14_OCCOR-01/analyze_occor.py', '../2026-11-14_OCGEO-01/analyze_ocgeo.py',
       '../2026-11-14_OCGEO-01/analyze_ocgeo_test.py']
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()   # noqa: E731


def main():
    cur = {f: sha(os.path.join(HERE, f)) for f in OWN}
    path = os.path.join(HERE, 'prereg_hashes.json')
    if '--verify' in sys.argv:
        reg = json.load(open(path))['files']
        bad = [f for f in cur if reg.get(f) != cur[f]]
        if '--job' in sys.argv:
            name = sys.argv[sys.argv.index('--job') + 1]
            job = os.path.join(HERE, '..', '..', 'gha_jobs', f'{name}.sh')
            if name not in WRAPPERS or not os.path.isfile(job) or sha(job) != cur[WRAPPERS[name]]:
                bad.append(f'gha_jobs/{name}.sh не совпадает с шаблоном {WRAPPERS.get(name)}')
        print('сверка хешей:', 'расхождения ' + str(bad) if bad else 'совпало')
        sys.exit(1 if bad else 0)
    json.dump({'files': cur}, open(path, 'w'), ensure_ascii=False, indent=1)
    print('записано', len(cur))


if __name__ == '__main__':
    main()
