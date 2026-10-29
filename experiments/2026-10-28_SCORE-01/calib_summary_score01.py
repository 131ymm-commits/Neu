#!/usr/bin/env python3
"""SCORE-01: сводка калибровки моих ожиданий §5 (исходы — основная выборка; tools/self_calibration.py) и веса опор сводных по
§6 PREREG (pilot_power.json: P — меньшая мощность, min(P; 0,999); «не показано» — 0). Записан после результатов.
  python3 calib_summary_score01.py   → calib_score01.json и печать (run/calib_score01.log)"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
f = lambda x, d=4: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')


def main():
    src = open(os.path.join(ROOT, 'tools', 'self_calibration.py'), encoding='utf-8').read()
    ns = {'__file__': os.path.join(ROOT, 'tools', 'self_calibration.py')}
    exec(src.split('\ndef ')[0], ns)
    rows = [r for r in ns['ROWS'] if r[0] == 'SCORE-01']
    st = lambda rr: dict(n=len(rr), mean_p=sum(r[4] for r in rr) / len(rr), share=sum(r[5] for r in rr) / len(rr),
                         brier=sum((r[4] - r[5]) ** 2 for r in rr) / len(rr))
    out = dict(all=st(rows), opus=st([r for r in rows if '(opus)' in r[1]]), haiku=st([r for r in rows if '(haiku)' in r[1]]))
    cls = [r for r in ns['ROWS'] if 'после пилота' in (r[1] + str(r[-1])) and r[5] is not None]
    out['class_after_pilot'] = st(cls)
    for v in out.values():
        v['self_dec'] = v['mean_p'] - v['share']
    P = json.load(open(os.path.join(HERE, 'pilot_power.json')))
    A = json.load(open(os.path.join(HERE, 'analysis_score01.json')))
    bits = {}
    for c, v in P['comps'].items():
        a, p = max(v['alpha'], 0.001), min(v['power_low'], 0.999)
        rd = [A['readings'].get(f"{c}|{s}_{c.split('_')[1]}") for s in ('main', 'rep')]
        w = [math.log2(p / a) if x == 'подтверждено' else (math.log2((1 - p) / (1 - v['alpha'])) if x == 'опровергнуто' else 0.0) for x in rd]
        bits[c] = dict(readings=rd, bits_each=w, group_max=max(w), alpha=v['alpha'], power_low=v['power_low'])
    out['bits'] = bits
    json.dump(out, open(os.path.join(HERE, 'calib_score01.json'), 'w'), ensure_ascii=False, indent=1)
    for k in ('all', 'opus', 'haiku', 'class_after_pilot'):
        v = out[k]
        print(f"{k}: ожиданий {v['n']}, средняя уверенность {f(v['mean_p'])}, доля подтверждённых {f(v['share'])}, Брайер {f(v['brier'])}, самообман {f(v['self_dec'])}")
    for c, v in bits.items():
        print(f"{c}: чтения {v['readings']}, вес основной и повтора {', '.join(f(x, 2) for x in v['bits_each'])} бита, группа — {f(v['group_max'], 2)}")


if __name__ == '__main__':
    main()
