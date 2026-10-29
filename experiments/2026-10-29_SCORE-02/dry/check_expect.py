#!/usr/bin/env python3
"""SCORE-02, сухой прогон: сверка исходов веток (dry/analysis_<ветка>.json) с ожиданиями, записанными до запуска.
Первый прогон — dry/expect.json → dry/check_expect.log; второй (после LENSES-2) — dry/expect2.json → dry/check_expect2.log.
  python3 dry/check_expect.py [ожидания.json] [журнал.log]   → печать; код выхода 1, если хоть одно ожидание не совпало"""
import json
import os
import sys

D = os.path.dirname(os.path.abspath(__file__))


def main():
    ex_name = sys.argv[1] if len(sys.argv) > 1 else 'expect.json'
    log_name = sys.argv[2] if len(sys.argv) > 2 else 'check_expect.log'
    X = json.load(open(os.path.join(D, ex_name), encoding='utf-8'))
    log, bad, n = [], 0, 0
    for br, ex in X.items():
        if br.startswith('_'):
            continue
        R = json.load(open(os.path.join(D, f'analysis_{br}.json'), encoding='utf-8'))
        log.append(f'== ветка {br}: {ex["_why"]}')
        for kind, src in (('verdicts', lambda k: R['verdicts'].get(k, {}).get('outcome')), ('readings', lambda k: R['readings'].get(k)),
                          ('part_readings', lambda k: R['verdicts'].get(k, {}).get('reading')),
                          ('calib', lambda k: str(R['verdicts'].get(k, {}).get('calib'))),
                          ('coverage', lambda k: str(R['coverage'].get(k.split('|')[0], {}).get(k.split('|')[1]))),
                          ('status', lambda k: R['status'].get(k, {}).get('status'))):
            for k, want in ex.get(kind, {}).items():
                got = src(k)
                ok = got is not None and (got.startswith(want) if kind == 'status' else got == want)
                n += 1
                bad += not ok
                log.append(f'  {"совпало" if ok else "НЕ СОВПАЛО"}: {kind} {k} — ждал «{want}», вышло «{got}»')
    log.append(f'итог: ожиданий {n}, не совпало {bad}')
    open(os.path.join(D, log_name), 'w', encoding='utf-8').write('\n'.join(log) + '\n')
    print('\n'.join(log))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
