#!/usr/bin/env python3
"""LENSES-2: сверка fastlib с кодом опыта (score02_lib) на пилоте и на evals сухого прогона: точечные AUC, карта огрубления,
интервалы бутстрепа при том же зерне. Запуск: python3 validate_fastlib.py <папка копии опыта>"""
import os
import sys
import zlib

import numpy as np

X = sys.argv[1]
sys.path.insert(0, X)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score02_lib as L  # noqa: E402
import fastlib as F  # noqa: E402

B = 2000
for stage, d in (('pilot_opus', None), ('pilot_haiku', None), ('main_opus', os.path.join(X, 'dry', 'evals')), ('rep_haiku', os.path.join(X, 'dry', 'evals'))):
    J = L.load(stage, d)
    tasks = sorted(J)
    M = L.measures(J, tasks)
    cm_repo, lv_repo = L.coarse_map(J, tasks)
    cm_fast, lv_fast = F.coarse_map(J, tasks)
    H = F.prep(J, tasks)
    one = np.ones((1, len(tasks)))
    pa = F.boot_auc(H['agree'], one)[0]
    ps = F.boot_auc(H['single'], one)[0]
    pc = F.boot_auc(H['single_c'], one)[0]
    print(f"{stage}: карта совпала: {cm_repo == cm_fast}; AUC agree {M['agree']['auc2']:.12f} / {pa:.12f}; single {M['single']['auc2']:.12f} / {ps:.12f}; "
          f"single_c {M['single_c']['auc2']:.12f} / {pc:.12f}")
    specs = [('auc2', 'agree', 'single'), ('auc2', 'agree', 'single_c')]
    BS = L.bootstrap(J, tasks, specs, B=B, name=stage)
    rng = np.random.default_rng(zlib.crc32(f'SCORE-02|{stage}'.encode()))
    W = F.weights(rng, len(tasks), B)
    da = F.boot_auc(H['agree'], W)
    d1 = da - F.boot_auc(H['single'], W)
    d2 = da - F.boot_auc(H['single_c'], W)
    r1, r2 = np.array(BS[specs[0]]), np.array(BS[specs[1]])
    print(f"   бутстреп B = {B}: наибольшая |разность| agree − single {np.nanmax(np.abs(r1 - d1)):.2e}, agree − single_c {np.nanmax(np.abs(r2 - d2)):.2e}; "
          f"интервалы {L.ci95(list(r2))} / {F.ci95(d2)}")
