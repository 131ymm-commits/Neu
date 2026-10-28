#!/usr/bin/env python3
"""TRUST-04: расширение пилота DEMES_NOWITHIN на зёрна 1300–1319 (третья проверка по трём линзам, находка 4: доля срывов
по 2 из 10 оценена плохо). Те же зёрна агент-проверяльщик прогонял в копии кода; здесь — код репозитория, формат run().
Запуск из папки опыта: OMP_NUM_THREADS=1 python3 pilot/v2b/run_nowithin.py"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import exp_trust_04 as E  # noqa: E402

SEEDS = list(range(1300, 1320))
t0 = time.time()
runs = [E.evolve4(s, 'DEMES_NOWITHIN') for s in SEEDS]
json.dump(dict(theory={'base': E.WORLDS['base'].theory()}, runs=runs,
               params=dict(L_EP=E.L_EP, G=E.G, SIG=E.SIG, WINDOW=E.WINDOW, ARMS={'DEMES_NOWITHIN': E.ARMS['DEMES_NOWITHIN']},
                           SEEDS=SEEDS, part='v2b', code_sha256=E.CODE_SHA256), seconds=time.time() - t0),
          open(os.path.join(HERE, 'results_nowithin_1300.json'), 'w'), default=float)
my, far = 0.9873, 0.6891
for r in runs:
    f = r['final']; br = f['wG_sd_groups'] > 0.5 or f['V_within'] > 0.1
    print(r['seed'], f"u {(f['wG'] - far) / (my - far):+.4f}", f"SD между {f['wG_sd_groups']:.4f}", f"V_внутри {f['V_within']:.4f}", 'срыв' if br else '')
print(f'готово за {time.time() - t0:.0f} с')
