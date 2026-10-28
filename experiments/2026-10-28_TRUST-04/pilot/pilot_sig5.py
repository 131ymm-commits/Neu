#!/usr/bin/env python3
"""TRUST-04, дополнительный пилот рук шага мутации ×5 (добавлены после независимой реализации, ERRORS № 111):
DEMES_SIG5 и POOLED_SIG5 на пилотных зёрнах 1100–1109 → pilot/results_trust_04_B_sig5.json (формат run()).
Запуск из папки опыта: OMP_NUM_THREADS=1 python3 pilot/pilot_sig5.py"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import exp_trust_04 as E  # noqa: E402

t0 = time.time(); arms = ['DEMES_SIG5', 'POOLED_SIG5']
runs = [E.evolve4(s, a) for s in E.PILOT_SEEDS for a in arms]
json.dump(dict(theory={k: w.theory() for k, w in E.WORLDS.items()}, runs=runs,
               params=dict(L_EP=E.L_EP, G=E.G, SIG=E.SIG, WINDOW=E.WINDOW, ARMS={a: E.ARMS[a] for a in arms},
                           SEEDS=E.PILOT_SEEDS, part='B_sig5'), seconds=time.time() - t0),
          open(os.path.join(HERE, 'results_trust_04_B_sig5.json'), 'w'), default=float)
print(f'готово за {time.time() - t0:.0f} с')
