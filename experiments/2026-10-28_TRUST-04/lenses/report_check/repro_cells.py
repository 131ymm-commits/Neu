#!/usr/bin/env python3
"""Воспроизводимость между машинами: пересчёт ячеек TRUST-04 копией зарегистрированного кода (sha256 41cc133b…)
на нынешней машине и сравнение бит в бит с results_trust_04_A.json (посчитан ДО перезапуска контейнера, ядро fc-v180)
и results_trust_04_B.json (ПОСЛЕ перезапуска, fc-v185). Запуск: python3 -I repro_cells.py ARM:SEED [ARM:SEED ...]"""
import json, os, sys, time, platform
S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(S, 'copyexp', '2026-10-28_TRUST-04'))
import numpy as np
import exp_trust_04 as E
D = '/home/claude/neu/experiments/2026-10-28_TRUST-04'
assert E.CODE_SHA256 == '41cc133b0ed563e0d81c921ad85b41e40ba1a2d3f090214e7130430c2c0387e0', E.CODE_SHA256
want = [a.split(':') for a in sys.argv[1:]]
parts = {p: None for p in ('A', 'B')}
res = []
for arm, seed in want:
    seed = int(seed); pt = E.ARMS[arm]['part']
    if parts[pt] is None:
        parts[pt] = {(r['seed'], r['arm']): r for r in json.load(open(f'{D}/results_trust_04_{pt}.json'))['runs']}
    ref = parts[pt][(seed, arm)]
    t0 = time.time(); r = json.loads(json.dumps(E.evolve4(seed, arm), default=float)); dt = time.time() - t0
    same_final = r['final'] == ref['final']
    same_traj = r['traj'] == ref['traj']
    nd = sum(1 for a, b in zip(r['traj'], ref['traj']) for k in a if a[k] != b[k])
    maxrel = max((abs(a[k] - b[k]) / (abs(b[k]) + 1e-300) for a, b in zip(r['traj'], ref['traj']) for k in a if a[k] != b[k]), default=0.0)
    first = next((a['g'] for a, b in zip(r['traj'], ref['traj']) if a != b), None)
    res.append(dict(arm=arm, seed=seed, part=pt, sec=round(dt, 1), final_bitwise=same_final, traj_bitwise=same_traj,
                    n_diff_values=nd, max_rel_diff=maxrel, first_diff_g=first,
                    wG_now=r['final']['wG'], wG_ref=ref['final']['wG']))
    print(res[-1], flush=True)
print(platform.platform(), np.__version__)
json.dump(res, open(os.path.join(S, 'repro_cells.json'), 'w'), ensure_ascii=False, indent=1)
