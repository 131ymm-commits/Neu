#!/usr/bin/env python3
"""TRUST-04: сводка калибровки ожиданий после записи исходов (tools/self_calibration.py) → calib_trust04.json для отчёта."""
import contextlib, importlib.util, io, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.argv = ['x', '--brief']
spec = importlib.util.spec_from_file_location('sc', os.path.join(ROOT, 'tools', 'self_calibration.py')); sc = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()):
    try:
        spec.loader.exec_module(sc)
    except SystemExit:
        pass
def summ(rows):
    p = [r[4] for r in rows]; o = [r[5] for r in rows]
    return dict(n=len(rows), conf=round(sum(p) / len(p), 4), share=round(sum(o) / len(o), 4),
                brier=round(sum((a - b) ** 2 for a, b in zip(o, p)) / len(p), 4), self_dec=round(sum(p) / len(p) - sum(o) / len(o), 4))
out = dict(trust04=summ([r for r in sc.ROWS if r[0] == 'TRUST-04']),
           post_pilot=summ([r for r in sc.ROWS if '(после пилота)' in r[1] and r[5] is not None]))
import re
sec = lambda f: float(re.search(r'готово за (\d+) с', open(os.path.join(HERE, f), encoding='utf-8').read()).group(1))
out['timing'] = dict(test_A=sec('run/test_A.log'), test_B=sec('run/test_B.log'), pilot_A=sec('pilot/v2/pilot_A.log'), pilot_B=sec('pilot/v2/pilot_B.log'))
out['timing']['ratio_test'] = round(out['timing']['test_B'] / out['timing']['test_A'], 2)
out['timing']['ratio_pilot'] = round(out['timing']['pilot_B'] / out['timing']['pilot_A'], 2)
json.dump(out, open(os.path.join(HERE, 'calib_trust04.json'), 'w'), ensure_ascii=False, indent=1); print(out)
