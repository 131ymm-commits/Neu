#!/usr/bin/env python3
"""SCORE-01: исходы ожиданий §5 в tools/self_calibration.py — по вердикту основной выборки (analysis_score01.json; повтор — в
заметке, в счёт не идёт: §5 PREREG). Исход 1 — «подтверждено», иначе 0 (в том числе «не показано»). Записан после результатов.
  python3 update_calibration_score01.py [--dry]"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))


def main():
    sys.path.insert(0, HERE)
    from analyze_score01 import PRED
    A = json.load(open(os.path.join(HERE, 'analysis_score01.json')))
    p = os.path.join(ROOT, 'tools', 'self_calibration.py')
    src = open(p, encoding='utf-8').read()
    n = 0
    for q in PRED:
        m, r = A['verdicts'][f"{q['id']}|main_{q['model']}"]['outcome'], A['verdicts'][f"{q['id']}|rep_{q['model']}"]['outcome']
        out = 1 if m == 'подтверждено' else 0
        pat = re.compile(r"(\('SCORE-01', '" + re.escape(q['id']) + r" \(" + q['model'] + r"\) [^']*', 'PREREG-SCORE-01 §5', 'вероятность', "
                         + re.escape(str(q['expect'])) + r"), None, '\(после пилота\) основная выборка; ждёт результата'\)")
        src, k = pat.subn(lambda mm: f"{mm.group(1)}, {out}, '(после пилота) основная: {m}; повтор: {r}; REPORT-SCORE-01.md')", src)
        assert k == 1, (q['id'], k)
        n += k
    if '--dry' in sys.argv:
        print('изменилось бы строк:', n)
    else:
        open(p, 'w', encoding='utf-8').write(src)
        print('исходы записаны:', n)


if __name__ == '__main__':
    main()
