#!/usr/bin/env python3
"""TRUST-03, пилот ручки при окончательном устройстве (3000 поколений, окно 2000): DEMES и COUNCIL при
m × n = 10 × 40, 20 × 20, 40 × 10, 80 × 5 (n/m = 4, 1, 0,25, 0,0625), зёрна 970–971, потоки 20–27 (не пересекаются
с руками 0–9). Первый пилот ручки (pilot/pilot_knob_trust_03.log, 1500 поколений) запускался командой в оболочке,
текст команды не сохранился (ERRORS № 106 (и)); этот скрипт — его замена.
Запуск из папки опыта: OMP_NUM_THREADS=1 python3 pilot4/pilot_knob.py → pilot4/pilot_knob.json, pilot4/pilot_knob.log"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import exp_trust_03 as E  # noqa: E402

SEEDS = [970, 971]
SHAPES = [(10, 40), (20, 20), (40, 10), (80, 5)]
rows = []
for i, (m, n) in enumerate(SHAPES):
    for kind, council in (('DEMES', False), ('COUNCIL', True)):
        name = f'KNOB_{kind}_{m}x{n}'
        E.ARMS[name] = dict(m=m, n=n, council=council, group_sel=True, stream=20 + 2 * i + int(council),
                            within_sel=True, common_eps=True)
        res = [E.evolve3(s, name) for s in SEEDS]
        w = [r['final']['wG'] for r in res]
        row = dict(arm=name, m=m, n=n, n_over_m=n / m, wG=w, wG_mean=sum(w) / len(w),
                   logloss=[r['final']['logloss'] for r in res], b=[r['final']['b'] for r in res])
        rows.append(row)
        line = (f"{name:18s} n/m {n / m:6.4f}: w_G {row['wG_mean']:.3f} ({', '.join(f'{x:.3f}' for x in w)}); "
                f"logloss {sum(row['logloss']) / len(w):.4f}")
        print(line, flush=True)
json.dump(dict(seeds=SEEDS, G=E.G, WINDOW=E.WINDOW, rows=rows), open(os.path.join(HERE, 'pilot_knob.json'), 'w'),
          ensure_ascii=False, indent=1)
