#!/usr/bin/env python3
"""LENSES-2: подбор параметров заглушки нуля под описательные числа пилота и поиск s, при котором AUC(agree) = AUC(single_c).
  SCORE02_COPY=<копия опыта> python3 explore_null.py <opus|haiku> <n задач> <s1,s2,…>"""
import collections
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fastlib as F  # noqa: E402
import nulldgp as G  # noqa: E402

model, n, ss = sys.argv[1], int(sys.argv[2]), [float(x) for x in sys.argv[3].split(',')]
base = dict(G.OPUS if model == 'opus' else G.HAIKU)
for kv in sys.argv[4:]:
    k, v = kv.split('=')
    base[k] = float(v)
for s in ss:
    P = dict(base, s=s)
    rng = np.random.default_rng(12345)
    J = G.gen_stage(rng, P, n)
    tasks = sorted(J)
    H = F.prep(J, tasks)
    one = np.ones((1, len(tasks)))
    aa, a1, ac = (float(F.boot_auc(H[k], one)[0]) for k in ('agree', 'single', 'single_c'))
    ag = [c for t in tasks for c, _ in J[t]['agree']]
    lev = collections.Counter(round(c, 3) for c in ag)
    acc = lambda src: np.mean([o for t in tasks for _, o in J[t][src]])
    conf = lambda src: np.mean([c for t in tasks for c, _ in J[t][src]])
    _, lv = F.coarse_map(J, tasks)
    print(f"{model} s = {s}: AUC single {a1:.3f}, single_c {ac:.3f}, agree {aa:.3f}; Δ = {aa - a1:+.4f}, Δc = {aa - ac:+.4f}; "
          f"точность single {acc('single'):.3f}, agree {acc('agree'):.3f}; уверенность single {conf('single'):.3f}; "
          f"уровни {', '.join(f'{k}: {v / len(ag):.2f}' for k, v in sorted(lev.items()))}")
