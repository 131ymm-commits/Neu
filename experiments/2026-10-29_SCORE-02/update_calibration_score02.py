#!/usr/bin/env python3
"""SCORE-02: исходы ожиданий §5 в tools/self_calibration.py — по вердикту основной выборки (analysis_score02.json; повтор — в
заметке, в счёт не идёт: §5 PREREG). Исход 1 — «подтверждено», иначе 0 (в том числе «не показано»). Часть с техническим чтением
(поле calib = False: «не показано (контекст)» или «не показано (потери)») — исход None, в заметке причина (PREREG §4, §5; LENSES-3, Л3-3).
Записан после регистрации, до данных теста.
  python3 update_calibration_score02.py [--dry] [--analysis <файл>]   (--analysis — для проверки на сухом прогоне)"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))


def main():
    sys.path.insert(0, HERE)
    from analyze_score02 import PRED
    a = sys.argv[1:]
    A = json.load(open(os.path.join(HERE, a[a.index('--analysis') + 1] if '--analysis' in a else 'analysis_score02.json'), encoding='utf-8'))
    p = os.path.join(ROOT, 'tools', 'self_calibration.py')
    src = open(p, encoding='utf-8').read()
    n = 0
    for q in PRED:
        vm, vr = A['verdicts'][f"{q['id']}|main_{q['model']}"], A['verdicts'][f"{q['id']}|rep_{q['model']}"]
        m, r = vm.get('reading', vm['outcome']), vr.get('reading', vr['outcome'])
        out = (1 if vm['outcome'] == 'подтверждено' else 0) if vm.get('calib', True) else None
        pat = re.compile(r"(\('SCORE-02', '" + re.escape(q['id']) + r" [^']*', 'PREREG-SCORE-02 §5', 'вероятность', "
                         + re.escape(str(q['expect'])) + r"), None, '\(после пилота\) основная выборка; ждёт результата'\)")
        note = f"(после пилота) основная: {m}; повтор: {r}; REPORT-SCORE-02.md" + ('' if out is not None else '; технический исход — в счёт не идёт')
        src, k = pat.subn(lambda mm: f"{mm.group(1)}, {out}, {note!r})", src)
        assert k == 1, (q['id'], k)
        n += k
    if '--dry' in sys.argv:
        print('изменилось бы строк:', n)
        for l in src.splitlines():
            if "('SCORE-02'," in l:
                print(l.strip()[:60], '…', l.strip()[-140:])
    else:
        open(p, 'w', encoding='utf-8').write(src)
        print('исходы записаны:', n)


if __name__ == '__main__':
    main()
