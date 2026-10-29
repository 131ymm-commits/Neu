#!/usr/bin/env python3
"""LENSES-3: бутстреп X1oc с картой огрубления на каждом пересэмпле (score02_lib.coarse_vec в measures_arr) против независимой
реализации пересчёта карты (fastlib.refit_single_c из LENSES-2: веса задач, свои доли уровней и средние ранги) на тех же пересэмплах
(то же зерно crc32('SCORE-02|<этап>')). Плюс: точечная оценка через coarse_vec = через coarse_map; nonempty — своим счётом.
  python3 validate_refit.py <копия опыта> <папка fastlib> [B]"""
import os
import sys
import zlib

import numpy as np

X, FL = sys.argv[1], sys.argv[2]
B = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
sys.path.insert(0, X)
sys.path.insert(0, FL)
import score02_lib as L  # noqa: E402
import fastlib as F  # noqa: E402

DRY = os.environ.get('DRY_EVALS', os.path.join(X, 'dry', 'evals'))   # evals ветки A3 из репозитория (только чтение): копия переписывается прогоном
for stage, d in (('pilot_opus', None), ('pilot_haiku', None), ('main_opus', DRY), ('rep_haiku', DRY)):
    J = L.load(stage, d)
    tasks = sorted(J)
    # точечная оценка: measures (coarse_vec по всей выборке) против coarse_map
    M = L.measures(J, tasks)
    cmap, _ = L.coarse_map(J, tasks)
    sc = np.array([cmap[c] for t in tasks for c, _ in J[t]['single']])
    so = np.array([o for t in tasks for _, o in J[t]['single']], bool)
    a_map = L.auc2_np(sc, so)
    # своё число непустых уровней
    av = sorted({c for t in tasks for c, _ in J[t]['agree']})
    ne = dict(agree=len(av), single_c=len(set(sc.tolist())))
    # бутстреп опыта и независимый пересчёт на тех же пересэмплах
    spec = ('auc2', 'agree', 'single_c')
    BS = np.array(L.bootstrap(J, tasks, [spec], B=B, name=stage)[spec])
    rng = np.random.default_rng(zlib.crc32(f'SCORE-02|{stage}'.encode()))
    W = F.weights(rng, len(tasks), B)
    H = F.prep(J, tasks)
    mine = F.boot_auc(H['agree'], W) - F.refit_single_c(J, tasks, W)
    fixed = F.boot_auc(H['agree'], W) - F.boot_auc(H['single_c'], W)
    print(f"{stage}: AUC single_c — coarse_vec {M['single_c']['auc2']:.12f}, coarse_map {a_map:.12f}; nonempty опыта {L.nonempty(J, tasks)}, своё {ne}; "
          f"бутстреп (B = {B}): наибольшая |разность| с независимым пересчётом {np.nanmax(np.abs(BS - mine)):.2e}; "
          f"SD: пересчёт {np.nanstd(BS):.4f}, фиксированная карта {np.nanstd(fixed):.4f}; интервал {L.ci95(list(BS))}")
